"""voice.Spec — request object passed to ``voice.generate()``.

Frozen dataclass so it's hashable (cache key derivation hashes the Spec
field set). All fields beyond ``voice_id`` are optional; defaults give
the conversational fast-path.

See plan v2 §2 for the full field rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Spec:
    """One request to ``voice.generate()``.

    Required:
        voice_id: name resolved against the voice registry.

    Optional (with conversational-fast-path defaults):
        chunk_strategy: ``"none"`` / ``"sentence"`` / ``"paragraph"``. Default ``"none"``.
        cache: enable content-addressed cache. Default ``False``.
        parallel: enable parallel-gen (v0.1+). Default ``False``; ``True`` raises
            ``NotImplementedError`` in v0.
        write_to: if set, also writes audio to this path. ``result.path`` populates.
        watermark: EU AI Act Article 50 opt-in. Default ``False``. v0 wires the
            flag through but actual watermark insertion is v0.X+; ``True`` raises
            ``NotImplementedError`` in v0.
        seed: deterministic synthesis knob. Default ``42``. Same (text, seed,
            spec) → same audio.
        extra: engine-specific params (model_id, sample_rate_hz, attention impl,
            etc.). Frozen via tuple-of-pairs conversion under the hood so the
            outer Spec stays hashable.
    """

    voice_id: str
    chunk_strategy: str = "none"
    cache: bool = False
    parallel: bool = False
    write_to: Path | None = None
    watermark: bool = False
    seed: int = 42
    extra: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        # Custom hash because `extra: dict` is unhashable by default; we
        # hash the sorted key-value tuple of extra for determinism.
        extra_items = tuple(sorted(self.extra.items()))
        return hash(
            (
                self.voice_id,
                self.chunk_strategy,
                self.cache,
                self.parallel,
                self.write_to,
                self.watermark,
                self.seed,
                extra_items,
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Spec):
            return NotImplemented
        return (
            self.voice_id == other.voice_id
            and self.chunk_strategy == other.chunk_strategy
            and self.cache == other.cache
            and self.parallel == other.parallel
            and self.write_to == other.write_to
            and self.watermark == other.watermark
            and self.seed == other.seed
            and self.extra == other.extra
        )


__all__ = ["Spec"]
