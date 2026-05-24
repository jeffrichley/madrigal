"""TTSBackend protocol + error taxonomy.

The ``TTSBackend`` Protocol is the seam between voice's top-level
``generate()`` and the concrete TTS engine. Real Qwen3-TTS, the
in-process Fake for tests, or any future ElevenLabs / OpenAI / etc.
adapter implements this Protocol.

The error taxonomy is pattern-pulled from agent-core-voice (battle-
tested by Pepper conversational use); preserving the class names
keeps consumers' ``except`` clauses compatible with the prior surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


class VoiceError(Exception):
    """Base for every error a TTSBackend may raise."""


class EmptyTextError(VoiceError):
    """Caller passed an empty or whitespace-only text."""


class TextTooLongError(VoiceError):
    """Text exceeds the model's token budget.

    Chunking strategies in ``voice.chunking`` should split text before it
    reaches a backend; this error fires when chunking didn't apply or the
    chunk itself is still over budget for the active model.
    """


class GPUOOMError(VoiceError):
    """The GPU ran out of memory during synthesis. Usually retryable."""


class VoiceNotPreparedError(VoiceError):
    """``synthesize()`` called for a voice_id that was never ``prepare_voice()``'d.

    Backends require an explicit ``prepare_voice()`` call before
    ``synthesize()`` so the per-voice prompt construction cost is paid
    once at startup, not per-utterance. The voice registry handles the
    pairing.
    """


@dataclass(frozen=True)
class VoiceInfo:
    """One configured voice in the registry.

    A voice is identified by ``voice_id`` (string the consumer uses) and
    materialized via ``ref_wav`` + ``ref_text`` (the ICL reference
    sample that teaches the model how this voice sounds). ``blend`` is
    an optional name of a voice-blending recipe (engine-dependent;
    carried through in v0, promoted to a first-class API in v0.X+).
    """

    voice_id: str
    ref_wav: Path
    ref_text: str
    blend: str | None = None


@runtime_checkable
class TTSBackend(Protocol):
    """The seam between voice.generate() and the concrete TTS engine.

    Backends are stateful: they hold loaded model weights + per-voice
    prepared prompts in memory. Construction typically loads the model
    (expensive); ``prepare_voice()`` constructs an ICL prompt for a
    specific voice (also expensive, once per voice); ``synthesize()`` is
    the per-utterance hot path.
    """

    def prepare_voice(self, voice_id: str, ref_wav: Path, ref_text: str) -> None:
        """Build + cache the prompt for ``voice_id``.

        Called once per voice at startup, before any ``synthesize()`` calls
        for that voice. Raises ``FileNotFoundError`` if ``ref_wav`` doesn't
        exist; engine-specific errors may also surface here.
        """

    def synthesize(self, voice_id: str, text: str, seed: int) -> tuple[bytes, float]:
        """Generate audio for an already-prepared voice.

        Returns ``(wav_bytes, generation_s)`` — the audio as WAV-format
        bytes, plus elapsed seconds for cost/perf tracking. Raises a
        ``VoiceError`` subclass on any failure the caller should surface.
        """


__all__ = [
    "EmptyTextError",
    "GPUOOMError",
    "TextTooLongError",
    "TTSBackend",
    "VoiceError",
    "VoiceInfo",
    "VoiceNotPreparedError",
]
