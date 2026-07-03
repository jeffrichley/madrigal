"""Qwen3-TTS backend with in-context-learning voice cloning.

Real backend. Lazy-imports ``soundfile``, ``torch``, and ``qwen_tts`` inside
``__init__`` so the rest of ``madrigal.engine`` is importable on hosts without
these optional deps installed (CI runners, dev machines without GPU, etc.).

Real Qwen synthesis requires the user to install ``qwen-tts`` separately
— it's not on PyPI today. agent_core releases ship the wheel as an
asset (``qwen_tts-0.1.1-py3-none-any.whl``); consumers can pip-install
that directly or set up a local mirror.

Built-in voice cloning per plan §2: a `voices.yaml` row with `ref_wav` +
`ref_text` is all that's needed; ``prepare_voice()`` builds the ICL
prompt at startup, then ``synthesize()`` is the per-utterance hot path
with no further training cost.
"""

from __future__ import annotations

import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from madrigal.engine.protocol import (
    EmptyTextError,
    GPUOOMError,
    VoiceNotPreparedError,
)

log = logging.getLogger(__name__)


class QwenTTSBackend:
    """Real backend: loads Qwen3-TTS once, holds ICL prompts per voice.

    Raises ``ImportError`` at construction if ``qwen-tts`` or ``torch``
    aren't installed. The error message names what to install so users
    aren't left guessing.
    """

    def __init__(
        self,
        *,
        model_path: str,
        device: str = "cuda:0",
        attn_implementation: str = "sdpa",
    ) -> None:
        try:
            import soundfile as sf
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise ImportError(
                "QwenTTSBackend requires `soundfile`, `qwen-tts`, and `torch`. "
                "Install soundfile via `pip install soundfile`. Install qwen-tts "
                "from agent_core's GitHub releases (qwen_tts-0.1.1-py3-none-any.whl) "
                "or vendor it locally. Install torch via `pip install torch` (or your "
                "platform's recommended install command for CUDA). "
                f"Original ImportError: {exc}"
            ) from exc

        self._sf = sf
        self._torch = torch
        self._device = device
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                f"QwenTTSBackend configured device={device!r} but CUDA is not "
                "available on this host. Set device='cpu' (slow but works) or "
                "fix the CUDA install."
            )
        log.info(
            "loading Qwen3-TTS: model_path=%s device=%s attn=%s",
            model_path,
            device,
            attn_implementation,
        )
        self._model = Qwen3TTSModel.from_pretrained(
            model_path,
            device_map=device,
            torch_dtype=torch.bfloat16,
            attn_implementation=attn_implementation,
        )
        self._prompts: dict[str, Any] = {}

    def prepare_voice(self, voice_id: str, ref_wav: Path, ref_text: str) -> None:
        ref_wav = Path(ref_wav)
        if not ref_wav.exists():
            raise FileNotFoundError(f"ref_wav not found: {ref_wav}")
        prompt = self._model.create_voice_clone_prompt(
            ref_audio=str(ref_wav),
            ref_text=ref_text,
        )
        self._prompts[voice_id] = prompt
        log.info("voice %r prepared", voice_id)

    def _invoke_model(
        self,
        text_or_texts: str | list[str],
        voice_clone_prompt: Any,
        seed: int,
        oom_msg: str | None = None,
    ) -> tuple[list[Any], Any]:
        """Seed the torch RNG, call generate_voice_clone, map OOM → GPUOOMError.

        Returns ``(wavs, sample_rate)`` from the model. ``wavs`` is always a
        list — single-text calls return a 1-element list; batch calls return N.
        ``oom_msg`` overrides the default GPUOOMError message (useful for batch
        callers that can suggest remedies like reducing max_batch_size).
        """
        self._torch.manual_seed(seed)
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(seed)
        try:
            # Qwen3-TTS raises RuntimeError (not a typed subclass) for GPU OOM.
            wavs, sample_rate = self._model.generate_voice_clone(
                text=text_or_texts,
                language="english",
                voice_clone_prompt=voice_clone_prompt,
            )
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower():
                raise GPUOOMError(oom_msg or str(exc)) from exc
            raise
        return wavs, sample_rate

    def _encode_wav_array(self, wav_array: Any, sample_rate: Any) -> bytes:
        """Encode a wav array (int16/float32) to PCM_16 WAV bytes via soundfile."""
        buf = BytesIO()
        self._sf.write(buf, wav_array, int(sample_rate), format="WAV", subtype="PCM_16")
        return buf.getvalue()

    def synthesize(self, voice_id: str, text: str, seed: int) -> tuple[bytes, float]:
        """Generate audio for an already-prepared voice. Returns (wav_bytes, gen_s)."""
        if voice_id not in self._prompts:
            raise VoiceNotPreparedError(f"voice {voice_id!r} not prepared")
        if not text.strip():
            raise EmptyTextError("text is empty or whitespace-only")

        prompt = self._prompts[voice_id]
        start = time.monotonic()

        # Seed for determinism — same (voice, text, seed) → same audio.
        wavs, sample_rate = self._invoke_model(text, prompt, seed)
        wav_bytes = self._encode_wav_array(wavs[0], sample_rate)

        generation_s = time.monotonic() - start
        log.debug(
            "synthesized voice=%r len=%d seed=%d gen=%.3fs bytes=%d",
            voice_id,
            len(text),
            seed,
            generation_s,
            len(wav_bytes),
        )
        return wav_bytes, generation_s

    def synthesize_batch(
        self, voice_id: str, texts: list[str], seed: int
    ) -> tuple[list[bytes], list[float]]:
        """Native Qwen3-TTS batched synthesis via generate_voice_clone list-mode.

        Calls ``self._model.generate_voice_clone(text=texts, language="english",
        voice_clone_prompt=[prompt]*N)`` once for the whole batch — one
        GPU inference pass for N items, vs. N separate passes the
        single-shot path would do. Real speedup is ~5-10x on a single
        GPU for typical sentence-length texts.

        Empty batch returns ``([], [])`` without invoking the model.
        Per-item timing is approximated by equal apportion
        (``per_item_s = total_s / len(texts)``) since the engine
        doesn't expose per-item wall-time. Total wall-time is exact.
        See spec §8 known limit.
        """
        if voice_id not in self._prompts:
            raise VoiceNotPreparedError(f"voice {voice_id!r} not prepared")
        if not texts:
            return [], []
        for t in texts:
            if not t.strip():
                raise EmptyTextError("text is empty or whitespace-only")

        prompt = self._prompts[voice_id]
        start = time.monotonic()

        oom_msg = (
            f"GPU OOM during synthesize_batch with N={len(texts)}. "
            "Reduce Spec.max_batch_size or use a coarser chunk_strategy."
        )
        wavs, sample_rate = self._invoke_model(
            texts,
            prompt * len(texts),  # list-multiply: broadcast the 1-element prompt to N copies for batch mode
            seed,
            oom_msg=oom_msg,
        )

        total_s = time.monotonic() - start
        per_item_s = total_s / len(texts)  # approximation: the engine returns only total wall-time, not per-item
        timings = [per_item_s] * len(texts)
        audio_bytes_list = [self._encode_wav_array(w, sample_rate) for w in wavs]

        log.debug(
            "synthesize_batch voice=%r N=%d seed=%d total=%.3fs per_item~%.3fs",
            voice_id,
            len(texts),
            seed,
            total_s,
            per_item_s,
        )
        return audio_bytes_list, timings
