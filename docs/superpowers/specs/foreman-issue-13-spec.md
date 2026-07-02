# Spec: refactor QwenTTSBackend — extract WAV/model helpers + hoist soundfile import (issue #13)

## Goal

Polish `packages/madrigal/src/madrigal/engine/qwen.py` without changing behavior:
extract two private helpers to shrink oversized methods, consolidate the duplicated
`soundfile` lazy-import into `__init__` alongside `torch`/`qwen_tts`, and add
targeted inline comments on non-obvious control flow.

For issue #13.

## Acceptance criteria

- `synthesize()` body (excluding docstring) is under 25 lines.
- `synthesize_batch()` body (excluding its long docstring) is under 30 lines.
- A private method `_encode_wav_array(self, wav_array: Any, sample_rate: Any) -> bytes`
  exists on `QwenTTSBackend` and is the sole call site for `soundfile`/BytesIO WAV encoding.
- A private method `_invoke_model(self, text_or_texts: str | list[str],
  voice_clone_prompt: Any, seed: int, oom_msg: str | None = None)
  -> tuple[list[Any], Any]` exists, handles seed setup and `RuntimeError → GPUOOMError`
  wrapping, and is called by both `synthesize()` and `synthesize_batch()`.
- `import soundfile as sf` no longer appears inside any method body; instead it is
  imported inside `QwenTTSBackend.__init__`'s existing `try` block alongside
  `torch`/`qwen_tts`, and stored as `self._sf`.
- The module docstring's lazy-import sentence is updated to mention `soundfile`
  alongside `torch` and `qwen_tts`.
- Three short inline comments are added at the three control-flow points shown
  in the sub-request code examples (sub-requests 3 and 6).
- `just check` passes (ruff + mypy + pytest green). No test additions required.
- Public API is unchanged: no renames, no signature changes, no behavior differences.

## Approach

**Pattern**: Extract Method (Fowler refactoring catalogue). No GoF pattern fits — this
is purely mechanical decomposition of two methods that grew by accretion.

### The two target methods

`qwen.py`'s `QwenTTSBackend` has two methods that do too much:

- **`synthesize()`** (lines 95–143, 49 total lines): guard checks → fetch prompt →
  seed torch RNG → call `generate_voice_clone` → catch OOM → encode WAV → log → return.
  That is six distinct responsibilities in one method.
- **`synthesize_batch()`** (lines 145–215, 71 total lines): same structure, plus a
  longer guard loop and the `prompt * len(texts)` list-broadcast idiom.

Both methods duplicate an identical 5-line WAV-encoding block (`BytesIO + sf.write`),
and both duplicate a ~13-line block for seed setup + `generate_voice_clone` call +
`RuntimeError → GPUOOMError` wrapping. Extraction removes the duplication and brings
the public methods down to pure orchestration.

### Import audit

`import soundfile as sf` appears twice in method bodies: `synthesize()` line 128 and
`synthesize_batch()` line 199. `soundfile` is intentionally lazy-loaded (it is NOT
in `pyproject.toml` and NOT in `uv.lock`, meaning it is an optional external
dependency, the same category as `torch` and `qwen_tts`). The lazy-load rationale
is: `import madrigal.engine.qwen` must succeed on hosts without GPU/optional deps
installed. The current placement — deferred to method bodies — provides no practical
benefit over deferring to `__init__` alongside torch: any host without `soundfile`
can neither construct nor call `QwenTTSBackend`, so failing at construction time is
strictly better UX (clear error early vs. silent until `synthesize()` fires).

Resolution: add `import soundfile as sf` to `__init__`'s existing
`try: import torch; from qwen_tts import Qwen3TTSModel` block; capture as
`self._sf = sf`; expand the `except ImportError` message to name `soundfile`.
The module docstring's lazy-import sentence is updated to list `soundfile` alongside
`torch`/`qwen_tts`.

### Two helpers to extract

**`_invoke_model(self, text_or_texts, voice_clone_prompt, seed, oom_msg=None)`**
Captures: seed the torch RNG → call `self._model.generate_voice_clone()` → map
`RuntimeError` with "out of memory" substring to `GPUOOMError`. Returns
`(wavs, sample_rate)`. The callers pass the already-computed `voice_clone_prompt`
so the helper needs no knowledge of single-vs-batch difference:
- `synthesize()` passes `prompt` (the 1-element list as-is)
- `synthesize_batch()` passes `prompt * len(texts)` (broadcasts to N) and a specific
  `oom_msg` with the batch size hint

**`_encode_wav_array(self, wav_array, sample_rate)`**
Captures: `buf = BytesIO(); self._sf.write(buf, wav_array, int(sample_rate),
format="WAV", subtype="PCM_16"); return buf.getvalue()`. Replaces the duplicated block
in both `synthesize()` and `synthesize_batch()`.

### Three inline comments to add

The existing long comment blocks (e.g. the 6-line comment on `prompt * len(texts)`)
can be condensed into short inline notes at the right callsites:

1. **At `voice_clone_prompt=prompt * len(texts)` in `synthesize_batch()`**:
   `# list-multiply: broadcast the 1-element prompt to N copies for batch mode`
2. **At `per_item_s = total_s / len(texts)` in `synthesize_batch()`**:
   `# approximation: the engine returns only total wall-time, not per-item`
3. **Inside the `try` block in `_invoke_model()`, above the `generate_voice_clone` call**:
   `# Qwen3-TTS raises RuntimeError (not a typed subclass) for GPU OOM.`

## Sub-requests (topologically sorted)

1. **Add `soundfile` to the lazy-import block in `__init__`.**
   In `QwenTTSBackend.__init__` (lines 50–60), expand the `try` block to:
   ```python
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
   ```
   (The `self._torch = torch` assignment already exists at line 62; extend it, don't
   duplicate.)

2. **Update the module docstring lazy-import sentence (lines 4–5 of `qwen.py`).**
   Change:
   ```
   Real backend. Lazy-imports ``torch`` and ``qwen_tts`` inside ``__init__``
   so the rest of ``madrigal.engine`` is importable on hosts without torch
   installed (CI runners, dev machines without GPU, etc.).
   ```
   To:
   ```
   Real backend. Lazy-imports ``soundfile``, ``torch``, and ``qwen_tts`` inside
   ``__init__`` so the rest of ``madrigal.engine`` is importable on hosts without
   these optional deps installed (CI runners, dev machines without GPU, etc.).
   ```

3. **Add `_invoke_model()` private method** below `prepare_voice()` and above
   `synthesize()`:
   ```python
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
   ```

4. **Add `_encode_wav_array()` private method** below `_invoke_model()`:
   ```python
   def _encode_wav_array(self, wav_array: Any, sample_rate: Any) -> bytes:
       """Encode a wav array (int16/float32) to PCM_16 WAV bytes via soundfile."""
       buf = BytesIO()
       self._sf.write(buf, wav_array, int(sample_rate), format="WAV", subtype="PCM_16")
       return buf.getvalue()
   ```

5. **Refactor `synthesize()`** to use the two helpers. Replace the method body
   from the current 49-line version with:
   ```python
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
   ```

6. **Refactor `synthesize_batch()`** to use the two helpers. The docstring is
   preserved verbatim (it documents the approximated-timing known limit and the
   empty-batch contract); only the method body changes:
   ```python
   def synthesize_batch(
       self, voice_id: str, texts: list[str], seed: int
   ) -> tuple[list[bytes], list[float]]:
       """<existing docstring unchanged>"""
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
   ```

7. **Run `just check`** and fix any issues ruff/mypy flag (likely: `Any` type annotations
   in the new helpers require `from typing import Any` which is already imported). Do
   not silence the linter; investigate and fix.

## File-level changes

| File | Change |
|------|--------|
| `packages/madrigal/src/madrigal/engine/qwen.py` | All changes: hoist soundfile import to `__init__`, update module docstring, add `_invoke_model()` and `_encode_wav_array()` private methods, refactor `synthesize()` and `synthesize_batch()` to use them. |

No other files are touched. No test files are added (the issue scopes this as refactor-only).

## Alternatives considered

- **Hoist `soundfile` to true module level** (top-of-file `import soundfile as sf`). Rejected:
  the module docstring's explicit design goal is "importable on hosts without [optional deps]
  installed". Moving soundfile to module level means `import madrigal.engine.qwen` fails on
  any system without libsndfile, breaking the invariant for CI runners and non-GPU dev
  machines. The `__init__`-level hoist gives the same "fail early with a clear error" UX
  improvement over method-body imports without breaking the module-import invariant.
- **Extract only `_encode_wav_array()`, leave `_invoke_model()` separate in each method**.
  Rejected: the seed-setup + OOM-wrapping block is also duplicated between `synthesize()`
  and `synthesize_batch()`. Extracting only the WAV helper brings `synthesize()` to ~40
  lines (still over ~30) and leaves the seed/OOM duplication in place. Both extractions
  together achieve the issue's size target and remove all the duplication.
- **Do nothing; the methods are commented and comprehensible**. Rejected: `synthesize_batch()`
  at 71 lines mixes guards, model invocation, and output encoding in one scope. The
  `import soundfile as sf` inside both methods will confuse future readers ("why is this
  inside the method?"). The refactoring has a measurable payoff.

## Open questions

None. The issue's code-level framing ("synthesis-dispatch code in the endpoint handler",
"build the synthesis spec") matches `QwenTTSBackend.synthesize()` / `synthesize_batch()`
in `qwen.py`; the "build synthesis spec" maps to the model-invocation setup extracted
into `_invoke_model()`. All `soundfile` lazy-import rationale verified against actual
`pyproject.toml` and `uv.lock`. No behavioral changes needed.

## Out of scope

- Renaming any public methods (`synthesize`, `synthesize_batch`, `prepare_voice`) or
  changing their signatures.
- Adding test files — the issue explicitly marks "Test additions (refactor only)" as out of scope.
- Changing the `generate.py` orchestrator. That file already has clean helper decomposition.
- Changing any files outside `engine/qwen.py` (`_wav.py`, `generate.py`, `registry/`,
  `cache/`, etc.).
- Bumping VERSION or editing CHANGELOG — release-please derives those from the merged
  conventional-commit PR title.
