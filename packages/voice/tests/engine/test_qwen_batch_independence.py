"""LOAD-BEARING acceptance criterion (per the never-done-without-running rule).

Determines whether v0.1 can ship with cache + parallel composing freely
(item-independent path) or whether they must be mutually exclusive
(item-coupled fallback). The test result selects which path is active
when we declare done.

Per parallel-gen-design.md §7.1 + §0 preamble:
- This test MUST run + pass on real Qwen3-TTS before v0.1 is declared done.
- Tagged `@pytest.mark.real_engine`; skipped without VOICE_REAL_ENGINE_OK=1.
- Done-gate convention: declaring v0.1 done requires VOICE_REAL_ENGINE_OK=1
  on the validation run that collects + passes this test. The done-gate is
  procedural (developer discipline + PR brief asserts it), not enforced by
  tooling.

If this test FAILS (engine batching is item-coupled), v0.1 must be amended
to add the cache+parallel mutually-exclusive raise per spec §5 before
declaring done.

Required env vars when VOICE_REAL_ENGINE_OK=1:
- VOICE_TEST_MODEL_PATH: filesystem path to Qwen3-TTS model
- VOICE_TEST_REF_WAV: filesystem path to a reference WAV
- VOICE_TEST_REF_TEXT: reference text matching the WAV
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_engine


@pytest.mark.skipif(
    not os.environ.get("VOICE_REAL_ENGINE_OK"),
    reason=(
        "Requires real Qwen3-TTS engine (torch + qwen-tts + GPU). "
        "Set VOICE_REAL_ENGINE_OK=1 + VOICE_TEST_MODEL_PATH/REF_WAV/REF_TEXT to run. "
        "Per the never-done-without-running rule (2026-05-24): v0.1 cannot ship "
        "without running this test."
    ),
)
def test_batch_item_independence_empirical() -> None:
    """Does `synthesize_batch(["a", "b"], seed=42)` produce same audio for "a"
    as `synthesize_batch(["a"], seed=42)` does?

    If YES (item-independent): cache + parallel compose freely; standard
        path active; spec §3 + §4 unchanged.
    If NO (item-coupled): cache + parallel must be mutually exclusive on
        this backend; spec §5 fallback active; orchestrator must raise
        ValueError when both flags are set.
    """
    from voice.engine import QwenTTSBackend

    model_path = os.environ.get("VOICE_TEST_MODEL_PATH")
    ref_wav_path = os.environ.get("VOICE_TEST_REF_WAV")
    ref_text = os.environ.get("VOICE_TEST_REF_TEXT")

    assert model_path, "VOICE_TEST_MODEL_PATH must be set"
    assert ref_wav_path, "VOICE_TEST_REF_WAV must be set"
    assert ref_text, "VOICE_TEST_REF_TEXT must be set"

    backend = QwenTTSBackend(
        model_path=model_path,
        device="cuda:0",
    )
    backend.prepare_voice("pepper", Path(ref_wav_path), ref_text)

    # Same text alone vs. in a batch with another text.
    alone_audios, _ = backend.synthesize_batch("pepper", ["Hello, world."], seed=42)
    in_batch_audios, _ = backend.synthesize_batch(
        "pepper", ["Hello, world.", "Second item, different text."], seed=42
    )

    if alone_audios[0] != in_batch_audios[0]:
        pytest.fail(
            "ITEM-COUPLED engine batching detected. v0.1 cache + parallel "
            "must be mutually exclusive on this backend; the orchestrator "
            "MUST raise ValueError when both flags are set. "
            "Spec §5 fallback path is active. "
            "Implementer: add the raise + remove the cache+parallel test "
            "path expectations; update the brief to Jeff naming the empirical "
            "result + the conditional-fallback being live."
        )
    # Else: item-independent. Cache + parallel compose freely. Standard path
    # active. v0.1 ships as designed.
