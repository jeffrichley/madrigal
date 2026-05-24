"""voice.generate — the orchestrator + voice.speak convenience wrapper.

Per plan v2 §1: single entry point with uniform Result return.

This module wires together:
- voice.Spec (request)
- voice.engine.TTSBackend (synthesis)
- voice.registry.Registry (voice_id → VoiceInfo)
- voice.cache.Cache (content-addressed)
- voice.chunking (text splitting)
- voice.Result (response, attribute-population-by-config)

See plan v2 §3 for the attribute population matrix.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from voice._cache_key import cache_key as _derive_cache_key
from voice._wav import concat_wavs, wav_duration_ms, wav_sample_rate_hz
from voice.cache import Cache, CacheEntry
from voice.chunking import chunk as _chunk_text
from voice.engine.protocol import TTSBackend
from voice.registry import Registry
from voice.result import Result
from voice.spec import Spec


def generate(
    text: str,
    spec: Spec,
    *,
    backend: TTSBackend,
    registry: Registry | None = None,
    cache: Cache | None = None,
    model_id: str = "default",
) -> Result:
    """Synthesize ``text`` per ``spec`` via ``backend``. See plan v2 §3 for return shape.

    The caller supplies the backend (already constructed + with the
    voice prepared via ``backend.prepare_voice``). Registry resolution
    happens here when ``spec.cache=True`` or when chunking needs to
    look up voice metadata (v0 does NOT auto-prepare voices on the
    backend; that's caller responsibility for explicit-lifecycle).

    ``cache`` is required when ``spec.cache=True``; passed-in so the
    caller controls its location/scope.
    """
    # 1. Deferred-feature guards.
    if spec.parallel:
        raise NotImplementedError(
            "spec.parallel=True is deferred to v0.1. "
            "v0 supports single-text synthesis only."
        )
    if spec.watermark:
        raise NotImplementedError(
            "spec.watermark=True is deferred to v0.X+. The flag is wired "
            "through Spec for forward-compatibility but watermark insertion "
            "is not yet implemented."
        )

    # 2. Cache requirement check.
    if spec.cache and cache is None:
        raise ValueError("spec.cache=True requires a Cache instance be passed via `cache=`")

    # 3. Voice resolution (Registry is optional but useful for diagnostics).
    if registry is not None:
        # Best-effort — raises KeyError if voice_id isn't in registry. The backend
        # may still synthesize without registry resolution if voice is pre-prepared.
        registry.get(spec.voice_id)

    # 4. Chunk the text.
    chunks = _chunk_text(text, spec.chunk_strategy)
    if not chunks:
        raise ValueError(
            f"chunk_strategy={spec.chunk_strategy!r} produced no chunks "
            f"from input (text was empty or whitespace-only)"
        )

    # 5. Synthesize each chunk (with cache lookup if enabled).
    per_chunk_audios: list[bytes] = []
    per_chunk_timings: list[float] = []
    per_chunk_manifest: list[dict[str, Any]] = []
    per_chunk_cache_hits: list[bool] = []
    per_chunk_keys: list[str] = []

    for chunk_text in chunks:
        audio_bytes, gen_s, key, hit = _synthesize_chunk(
            text=chunk_text,
            spec=spec,
            backend=backend,
            cache=cache,
            model_id=model_id,
        )
        per_chunk_audios.append(audio_bytes)
        per_chunk_timings.append(gen_s)
        per_chunk_cache_hits.append(hit)
        if key is not None:
            per_chunk_keys.append(key)
        per_chunk_manifest.append(
            {
                "text": chunk_text,
                "cache_key": key,
                "cache_hit": hit,
                "generation_s": gen_s,
            }
        )

    # 6. Stitch the chunks into one audio blob.
    full_audio = concat_wavs(per_chunk_audios)
    sample_rate = wav_sample_rate_hz(full_audio) if full_audio else 16_000

    # 7. Build the Result per the population matrix.
    is_chunked = len(chunks) > 1 or spec.chunk_strategy != "none"
    any_hit = any(per_chunk_cache_hits)

    if is_chunked:
        # Chunked path: manifest + timings populated; cache_key None (per-chunk
        # keys live in the manifest); cache_hit reflects any-chunk-hit.
        result = Result(
            audio=full_audio,
            sample_rate_hz=sample_rate,
            manifest=per_chunk_manifest,
            timings=per_chunk_timings,
            cache_hit=any_hit,
        )
    else:
        # Single-chunk fast path: cache_key + cache_hit at top level; no manifest.
        single_key = per_chunk_keys[0] if per_chunk_keys else None
        result = Result(
            audio=full_audio,
            sample_rate_hz=sample_rate,
            cache_key=single_key,
            cache_hit=per_chunk_cache_hits[0] if per_chunk_cache_hits else False,
        )

    # 8. Optional file write.
    if spec.write_to is not None:
        spec.write_to.parent.mkdir(parents=True, exist_ok=True)
        spec.write_to.write_bytes(full_audio)
        result = replace(result, path=spec.write_to)

    return result


def speak(
    text: str,
    voice_id: str,
    *,
    backend: TTSBackend,
    registry: Registry | None = None,
    **spec_kwargs: Any,
) -> bytes:
    """Convenience wrapper: synthesize one utterance, return bytes.

    Equivalent to ``bytes(generate(text, Spec(voice_id=voice_id, **spec_kwargs), backend=backend, registry=registry))``.

    For batch synthesis with chunking, cache, or write-to-file, use
    ``generate()`` directly and inspect the returned ``Result``.
    """
    spec = Spec(voice_id=voice_id, **spec_kwargs)
    result = generate(text, spec, backend=backend, registry=registry)
    return bytes(result)


def _synthesize_chunk(
    *,
    text: str,
    spec: Spec,
    backend: TTSBackend,
    cache: Cache | None,
    model_id: str,
) -> tuple[bytes, float, str | None, bool]:
    """Synthesize a single chunk with optional cache lookup.

    Returns ``(wav_bytes, generation_s, cache_key_or_None, cache_hit)``.
    cache_key is None when ``spec.cache=False``; otherwise the
    sha256 hex digest.
    """
    if not spec.cache:
        # No cache — synthesize directly.
        audio, gen_s = backend.synthesize(spec.voice_id, text, spec.seed)
        return audio, gen_s, None, False

    # Cache enabled.
    assert cache is not None  # guarded above
    key = _derive_cache_key(spec=spec, text=text, model_id=model_id)
    hit = cache.get(key)
    if hit is not None:
        # Cache hit: skip synthesis. generation_s = 0.0 (no work done now).
        return hit.audio, 0.0, key, True

    # Cache miss: synthesize + store.
    audio, gen_s = backend.synthesize(spec.voice_id, text, spec.seed)
    audio_sha256 = hashlib.sha256(audio).hexdigest()
    sample_rate = wav_sample_rate_hz(audio) if audio else 0
    duration = wav_duration_ms(audio) if audio else 0
    entry = CacheEntry(
        audio=audio,
        sha256=audio_sha256,
        sample_rate_hz=sample_rate,
        duration_ms=duration,
        generation_s=gen_s,
        timestamp_utc=datetime.now(UTC).isoformat(),
    )
    cache.put(key, entry)
    return audio, gen_s, key, False


__all__ = ["generate", "speak"]
