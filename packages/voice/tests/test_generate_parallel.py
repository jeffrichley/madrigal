"""Integration tests for voice v0.1 parallel-gen orchestrator (UC1 + UC2).

Covers the §3 + §4 data-flow diagrams from parallel-gen-design.md:
- UC1: list-input + parallel=True → Result.audios populated
- UC2: chunked string + parallel=True → Result.audio (concat) populated
- Cache partition + reassemble (silent-shuffle catcher)
- cache_hit (any) + cache_fully_hit (all) semantics
- parallel_used flag
- max_batch_size sub-batching
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voice import Cache, Result, Spec, generate
from voice.engine import FakeTTSBackend


@pytest.fixture
def ref_wav(tmp_path: Path) -> Path:
    p = tmp_path / "ref.wav"
    p.write_bytes(b"placeholder")
    return p


@pytest.fixture
def backend(ref_wav: Path) -> FakeTTSBackend:
    b = FakeTTSBackend()
    b.prepare_voice("pepper", ref_wav, "ref text")
    return b


# ---------------------------------------------------------------------------
# UC1 — explicit batch (list-input + parallel=True)
# ---------------------------------------------------------------------------

class TestUC1ExplicitBatch:
    """list-input + parallel=True → Result.audios populated."""

    def test_basic_returns_audios_list(self, backend: FakeTTSBackend) -> None:
        result = generate(["one", "two", "three"], Spec(voice_id="pepper", parallel=True), backend=backend)
        assert isinstance(result, Result)
        assert result.audios is not None
        assert len(result.audios) == 3
        assert all(isinstance(a, bytes) for a in result.audios)
        assert result.audio is None  # UC1 doesn't populate .audio
        assert result.parallel_used is True
        assert result.timings is not None
        assert len(result.timings) == 3

    def test_input_order_preserved(self, backend: FakeTTSBackend) -> None:
        """audios[i] corresponds to texts[i]. Determinism enforces this."""
        result = generate(["alpha", "beta", "gamma"], Spec(voice_id="pepper", parallel=True), backend=backend)
        seq = [backend.synthesize("pepper", t, 42) for t in ["alpha", "beta", "gamma"]]
        assert result.audios == [s[0] for s in seq]

    def test_list_input_without_parallel_raises(self, backend: FakeTTSBackend) -> None:
        with pytest.raises(ValueError, match="list input requires"):
            generate(["a", "b"], Spec(voice_id="pepper", parallel=False), backend=backend)

    def test_empty_list_returns_empty_result(self, backend: FakeTTSBackend) -> None:
        result = generate([], Spec(voice_id="pepper", parallel=True), backend=backend)
        assert result.audios == []
        assert result.timings == []
        assert result.parallel_used is True

    def test_single_item_list(self, backend: FakeTTSBackend) -> None:
        """N=1 still goes through the batch path; .audios has one element."""
        result = generate(["only"], Spec(voice_id="pepper", parallel=True), backend=backend)
        assert result.audios is not None
        assert len(result.audios) == 1
        assert result.audio is None


class TestUC1WithCache:
    """list-input + parallel=True + cache=True: partition + reassemble."""

    def test_first_call_all_miss(self, backend: FakeTTSBackend, tmp_path: Path) -> None:
        cache = Cache(root=tmp_path / "cache")
        result = generate(
            ["a", "b", "c"],
            Spec(voice_id="pepper", parallel=True, cache=True),
            backend=backend,
            cache=cache,
        )
        assert result.cache_hit is False  # any() of zero hits = False
        assert result.cache_fully_hit is False
        assert result.manifest is not None
        assert len(result.manifest) == 3
        assert all(m["cache_hit"] is False for m in result.manifest)
        assert all(m["cache_key"] is not None for m in result.manifest)

    def test_second_call_all_hit(self, backend: FakeTTSBackend, tmp_path: Path) -> None:
        cache = Cache(root=tmp_path / "cache")
        spec = Spec(voice_id="pepper", parallel=True, cache=True)
        _ = generate(["a", "b", "c"], spec, backend=backend, cache=cache)
        r2 = generate(["a", "b", "c"], spec, backend=backend, cache=cache)
        assert r2.cache_hit is True  # any
        assert r2.cache_fully_hit is True  # all
        assert r2.manifest is not None
        assert all(m["cache_hit"] is True for m in r2.manifest)

    def test_mixed_partition_preserves_order(
        self, backend: FakeTTSBackend, tmp_path: Path
    ) -> None:
        """SILENT-SHUFFLE CATCHER. The load-bearing test.

        Prime cache with "a" and "c"; call with ["a", "b", "c"]. Orchestrator
        must partition [b] as miss, synthesize via backend.synthesize_batch,
        and reassemble [cached_a, new_b, cached_c] in input order.
        """
        cache = Cache(root=tmp_path / "cache")
        spec = Spec(voice_id="pepper", parallel=True, cache=True)

        # Prime with a + c.
        _ = generate(["a"], spec, backend=backend, cache=cache)
        _ = generate(["c"], spec, backend=backend, cache=cache)

        # Call with [a, b, c]: a + c hit; b miss + synthesized.
        result = generate(["a", "b", "c"], spec, backend=backend, cache=cache)

        # Verify input-order reassembly: each audio at index i matches direct
        # synthesis of texts[i].
        expected_a, _ = backend.synthesize("pepper", "a", 42)
        expected_b, _ = backend.synthesize("pepper", "b", 42)
        expected_c, _ = backend.synthesize("pepper", "c", 42)

        assert result.audios is not None
        assert result.audios[0] == expected_a
        assert result.audios[1] == expected_b
        assert result.audios[2] == expected_c

        # cache_hit any() True (a+c hit); cache_fully_hit all() False (b missed).
        assert result.cache_hit is True
        assert result.cache_fully_hit is False

        # Manifest reflects per-item hit status.
        assert result.manifest is not None
        assert result.manifest[0]["cache_hit"] is True
        assert result.manifest[1]["cache_hit"] is False
        assert result.manifest[2]["cache_hit"] is True


# ---------------------------------------------------------------------------
# UC2 — auto-parallel-on-chunk (str + chunking + parallel=True)
# ---------------------------------------------------------------------------

class TestUC2ChunkedParallel:
    """str + chunk_strategy + parallel=True → Result.audio (concat) populated."""

    def test_basic_returns_concat_audio(self, backend: FakeTTSBackend) -> None:
        result = generate(
            "First. Second. Third.",
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=True),
            backend=backend,
        )
        assert isinstance(result, Result)
        assert isinstance(result.audio, bytes)
        assert result.audios is None  # UC2 doesn't populate .audios
        assert result.parallel_used is True
        assert result.timings is not None
        assert len(result.timings) == 3

    def test_audio_is_concat_of_chunks(self, backend: FakeTTSBackend) -> None:
        """UC2's audio = concat of per-chunk audios."""
        text = "First. Second. Third."
        result = generate(
            text,
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=True),
            backend=backend,
        )
        # Compare against UC2 with parallel=False (sequential chunked v0 path).
        baseline = generate(
            text,
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=False),
            backend=backend,
        )
        # Same chunks + same sequential audio = same concat output.
        assert result.audio == baseline.audio

    def test_single_chunk_degenerates_to_v0_path(self, backend: FakeTTSBackend) -> None:
        """Long text with chunking that yields only 1 chunk → v0 path. parallel_used=False."""
        result = generate(
            "Just one sentence.",
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=True),
            backend=backend,
        )
        # Single sentence chunks to 1 chunk; no batching happened.
        assert result.parallel_used is False
        assert result.audio is not None

    def test_write_to_writes_concat(self, backend: FakeTTSBackend, tmp_path: Path) -> None:
        out = tmp_path / "out.wav"
        result = generate(
            "First. Second.",
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=True, write_to=out),
            backend=backend,
        )
        assert out.exists()
        assert out.read_bytes() == result.audio


class TestUC2WithCache:
    """UC2 + cache=True: same partition logic applied to chunks."""

    def test_first_call_all_miss(self, backend: FakeTTSBackend, tmp_path: Path) -> None:
        cache = Cache(root=tmp_path / "cache")
        result = generate(
            "First. Second.",
            Spec(voice_id="pepper", chunk_strategy="sentence", parallel=True, cache=True),
            backend=backend,
            cache=cache,
        )
        assert result.cache_hit is False
        assert result.cache_fully_hit is False
        assert result.manifest is not None
        assert len(result.manifest) == 2
        assert all(m["cache_hit"] is False for m in result.manifest)

    def test_second_call_all_hit_yields_same_audio(
        self, backend: FakeTTSBackend, tmp_path: Path
    ) -> None:
        cache = Cache(root=tmp_path / "cache")
        spec = Spec(
            voice_id="pepper", chunk_strategy="sentence", parallel=True, cache=True
        )
        r1 = generate("First. Second.", spec, backend=backend, cache=cache)
        r2 = generate("First. Second.", spec, backend=backend, cache=cache)
        assert r2.cache_hit is True
        assert r2.cache_fully_hit is True
        # Same audio on cache hit.
        assert r2.audio == r1.audio


# ---------------------------------------------------------------------------
# max_batch_size sub-batching
# ---------------------------------------------------------------------------

class TestMaxBatchSize:
    """Spec.max_batch_size slices large batches into sub-batches."""

    def test_unlimited_default(self, backend: FakeTTSBackend) -> None:
        """Default None passes the full list in one call. Equivalent output."""
        texts = ["a", "b", "c", "d", "e"]
        r_unlimited = generate(
            texts, Spec(voice_id="pepper", parallel=True, max_batch_size=None), backend=backend
        )
        r_sliced = generate(
            texts, Spec(voice_id="pepper", parallel=True, max_batch_size=2), backend=backend
        )
        # Same output regardless of slicing.
        assert r_unlimited.audios == r_sliced.audios

    def test_slicing_into_sub_batches(self, backend: FakeTTSBackend) -> None:
        """max_batch_size=2 on a 5-item list → 3 sub-batches (2 + 2 + 1)."""
        texts = [f"text_{i}" for i in range(5)]
        result = generate(
            texts,
            Spec(voice_id="pepper", parallel=True, max_batch_size=2),
            backend=backend,
        )
        assert result.audios is not None
        assert len(result.audios) == 5
        # Each audio matches direct synthesis.
        for i, t in enumerate(texts):
            expected, _ = backend.synthesize("pepper", t, 42)
            assert result.audios[i] == expected

    def test_slicing_with_cache(self, backend: FakeTTSBackend, tmp_path: Path) -> None:
        """Sub-batching + cache: partition still correct."""
        cache = Cache(root=tmp_path / "cache")
        spec = Spec(voice_id="pepper", parallel=True, cache=True, max_batch_size=2)
        texts = ["a", "b", "c", "d", "e"]
        _ = generate(texts, spec, backend=backend, cache=cache)
        # Second call: all hit.
        r2 = generate(texts, spec, backend=backend, cache=cache)
        assert r2.cache_fully_hit is True
        assert r2.audios is not None and len(r2.audios) == 5
