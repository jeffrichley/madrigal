# Spec: catch `wave.Error` in `_wav.py` and re-raise as typed `WavDecodingError` (issue #14)

## Goal

Stop bare `wave.Error` from escaping madrigal's synthesis path when a backend
returns malformed WAV bytes. The three private WAV helpers in
`packages/madrigal/src/madrigal/_wav.py` (`wav_sample_rate_hz`,
`wav_duration_ms`, `concat_wavs`) currently let `wave.Error` propagate raw,
so downstream consumers — the `agent-core-voice` adapter daemon noted in the
issue, the audiobook pipeline, Chrona narration — cannot distinguish "WAV
decoding failed" from any other engine/network/runtime failure.

Resolves [issue #14](https://github.com/jeffrichley/voice/issues/14).

## Acceptance criteria

- A new exception class `WavDecodingError(VoiceError)` is defined in
  `packages/madrigal/src/madrigal/engine/protocol.py` and exported from
  `madrigal.engine.protocol.__all__` and `madrigal.engine.__init__`.
- `wav_sample_rate_hz`, `wav_duration_ms`, and `concat_wavs` in
  `packages/madrigal/src/madrigal/_wav.py` each wrap their `wave.open(...)`
  block in `try`/`except wave.Error as exc` and `raise WavDecodingError(...) from exc`.
- The chained exception preserves the original `wave.Error`: catching
  `WavDecodingError` and reading `.__cause__` returns the original
  `wave.Error` instance.
- `concat_wavs` continues to raise `ValueError` (not `WavDecodingError`) for
  the mismatched-format path at `_wav.py:60-66` — that branch is a caller
  precondition violation, not a decoding failure.
- A new test file `packages/madrigal/tests/test_wav.py` covers:
  (a) each of the three helpers raises `WavDecodingError` when given
  malformed WAV bytes (e.g. `b"not a wav"`),
  (b) `__cause__` is a `wave.Error`,
  (c) `concat_wavs` still raises `ValueError` for the format-mismatch case,
  (d) happy-path round-trips remain unchanged.
- `packages/madrigal/tests/engine/test_protocol.py:test_error_taxonomy_descends_from_voice_error`
  is extended to assert `issubclass(WavDecodingError, VoiceError)`.
- `just check` passes (lint + typecheck + tests).
- No new dependencies. No changes outside `_wav.py`, `engine/protocol.py`,
  `engine/__init__.py`, and the two test files named above.

## Approach

The issue framing references a "voice endpoint" / "daemon" and a hypothetical
`_WavPhaseError` — neither of those exists in this repo. madrigal is a pure
library (per `CLAUDE.md` and `AGENTS.md`); the daemon belongs to the
`agent-core-voice` consumer. The fix the consumer needs is for madrigal to
emit a *typed* error at the WAV-decode boundary, so any consumer (daemon,
audiobook batch job, Chrona narration) can `except` on a stable name. The
existing public taxonomy in `packages/madrigal/src/madrigal/engine/protocol.py`
already follows this pattern: `VoiceError` as the base, then concrete
subclasses (`EmptyTextError`, `TextTooLongError`, `GPUOOMError`,
`VoiceNotPreparedError`), all exported through `madrigal.engine`. We extend
that taxonomy with `WavDecodingError(VoiceError)` and adopt the no-underscore,
exported-from-`madrigal.engine` naming convention rather than the issue's
suggested `_WavPhaseError` (which would imply a private/internal symbol and
break the consumer's ability to import it).

The catch happens *inside* the three helpers in `_wav.py`, not at the
orchestrator call sites in `generate.py`. There are eight call sites
(`generate.py:210, 211, 304, 329, 378, 379, 528, 529`) across
`_generate_v0_sequential`, `_generate_uc1_batch`,
`_generate_uc2_chunked_parallel`, and `_cache_put`. Wrapping at the helper
boundary keeps the typed-error contract in one place — every existing and
future caller benefits without repeating the try/except — and matches
`_wav.py`'s own module docstring, which calls out the helpers as the
sanctioned WAV-handling surface ("Consumers needing WAV manipulation beyond
this should use ``soundfile`` or ``wave`` directly").

Each helper's `try` covers exactly the `wave.open(BytesIO(...)) as w: ...`
block. The `ValueError` branch in `concat_wavs` for format mismatch
(`_wav.py:60-66`) stays as-is — that's a precondition error (caller passed
inconsistent WAVs), distinct from "the bytes don't parse as WAV". The
docstrings on the three helpers are updated to document the new
`WavDecodingError` raise alongside the existing behaviour.

`__cause__` chaining via `raise ... from exc` is non-negotiable per the
issue. Tests assert the chain explicitly so a future refactor can't
accidentally drop the `from`.

## Sub-requests (topologically sorted)

1. In `packages/madrigal/src/madrigal/engine/protocol.py`, add
   `class WavDecodingError(VoiceError): ...` with a one-line docstring
   ("WAV bytes returned by a backend (or passed to a wav helper) could not
   be decoded. ``__cause__`` is the underlying ``wave.Error``."). Append
   `"WavDecodingError"` to the module's `__all__` list, preserving alphabetical
   order.
2. In `packages/madrigal/src/madrigal/engine/__init__.py`, add
   `WavDecodingError` to the `from madrigal.engine.protocol import (...)`
   block and to the module-level `__all__`, preserving alphabetical order.
3. In `packages/madrigal/src/madrigal/_wav.py`, import `WavDecodingError`
   (`from madrigal.engine.protocol import WavDecodingError`). In each of
   `wav_sample_rate_hz`, `wav_duration_ms`, and `concat_wavs`, wrap the
   `with wave.open(...) as w:` block in `try` / `except wave.Error as exc:
   raise WavDecodingError(...) from exc`. Use a short, helper-specific
   message (e.g. `"failed to decode WAV bytes for sample-rate read"`).
   Update each docstring's `Raises` sentence accordingly.
4. Extend `packages/madrigal/tests/engine/test_protocol.py::test_error_taxonomy_descends_from_voice_error`
   to import `WavDecodingError` from `madrigal.engine` and assert
   `issubclass(WavDecodingError, VoiceError)`.
5. Create `packages/madrigal/tests/test_wav.py` with the test cases listed
   in Acceptance criteria. Use `pytest.raises(WavDecodingError) as excinfo`
   and assert `isinstance(excinfo.value.__cause__, wave.Error)`. Include a
   round-trip happy-path test per helper to lock in current behaviour.
6. Run `just check`. If lint flags import-order or `__all__` order, fix
   in-place; do not silence the linter.

## File-level changes

| File | Change |
|------|--------|
| `packages/madrigal/src/madrigal/engine/protocol.py` | Add `WavDecodingError(VoiceError)` class + extend `__all__`. |
| `packages/madrigal/src/madrigal/engine/__init__.py` | Re-export `WavDecodingError` + extend `__all__`. |
| `packages/madrigal/src/madrigal/_wav.py` | Wrap `wave.open(...)` blocks in three helpers with `try/except wave.Error -> WavDecodingError`, update docstrings, add import. |
| `packages/madrigal/tests/engine/test_protocol.py` | Add `WavDecodingError` subclass assertion to existing taxonomy test. |
| `packages/madrigal/tests/test_wav.py` (NEW) | Tests for typed-error raise, `__cause__` chaining, happy-path round-trips, and the preserved `ValueError` format-mismatch path. |

## Alternatives considered

- **Catch at the eight `generate.py` call sites instead of at the helper
  boundary.** Rejected: duplicates the try/except in four functions, and
  any future caller (a new orchestrator path, a downstream consumer that
  imports `_wav` directly during a debug session) would have to remember to
  repeat the pattern. Centralising at the helper is one place to get right.
- **Use the issue's literal suggested name `_WavPhaseError`.** Rejected: the
  leading underscore signals "private/internal", which contradicts the goal
  of giving consumers a stable name to `except` on. The existing taxonomy
  (`EmptyTextError`, `GPUOOMError`, etc.) has no underscore prefix and is
  re-exported from `madrigal.engine`. The issue body explicitly invites
  this remapping ("or whatever the project's domain error type is —
  investigate the existing error hierarchy first").
- **Make `WavDecodingError` subclass `ValueError` as well as `VoiceError`.**
  Rejected: dual inheritance would let existing `except ValueError` catches
  in consumer code silently swallow decoding errors, defeating the point of
  the typed surface. Distinct classes, distinct semantics.
- **Do nothing; let consumers `except wave.Error` themselves.** Rejected:
  that forces every consumer to know madrigal uses the stdlib `wave` module
  internally — a leaky abstraction. The whole point of a `VoiceError`
  hierarchy is so consumers don't need to know which library decoded the
  bytes.

## Open questions

None. The issue's framing (endpoint/daemon/`_WavPhaseError`) was inaccurate
for this repo, but the underlying ask (typed error at the WAV-decode
boundary, with `from` chaining) maps unambiguously to the existing
`VoiceError` taxonomy.

## Out of scope

- Any change to `agent-core-voice` (lives in a different repo; that
  consumer's daemon will adopt the new `WavDecodingError` in its own PR
  once madrigal ships).
- Re-routing `ValueError` from `concat_wavs`'s format-mismatch branch into
  the new taxonomy. That's a separate API change with its own compatibility
  implications.
- Adding new metrics, logging, or error codes around WAV decoding. The
  issue asks only for a typed exception; instrumentation belongs to a
  follow-up if operators need it.
- Adding a `WavDecodingError` raise from `engine/qwen.py` or `engine/fake.py`
  themselves. Both currently produce well-formed WAV bytes by construction;
  if a future backend can produce bytes that fail decode, the helper-level
  catch already covers the path that decodes them.
- Bumping the VERSION or editing CHANGELOG; release-please derives those
  from the conventional-commit subject of the merged PR.
