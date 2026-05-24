"""voice.Result — uniform response from ``voice.generate()``.

Per plan v2 §3: attribute population varies by Spec configuration; the
return TYPE is always Result. Type-checker stays happy; consumers
discover what's populated for their config via the population matrix.

``bytes(result)`` is the conversational fast-path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Result:
    """One response from ``voice.generate()``.

    See plan v2 §3 for the attribute-population matrix (which fields are
    populated for which Spec configurations).
    """

    audio: bytes | None = None
    audios: list[bytes] | None = None
    path: Path | None = None
    manifest: list[dict[str, Any]] | None = None
    timings: list[float] | None = None
    sample_rate_hz: int = 16_000
    cache_key: str | None = None
    cache_hit: bool = False

    def __bytes__(self) -> bytes:
        """Conversational fast-path: ``bytes(result)`` → the audio.

        Raises ``ValueError`` if ``audio`` is None (e.g., parallel-gen
        result where only ``audios`` is populated). Callers needing
        list-of-bytes should inspect ``.audios`` directly.
        """
        if self.audio is None:
            raise ValueError(
                "Result has no .audio (parallel-gen result with .audios? "
                "file-write-only result?). Inspect .audios / .path instead."
            )
        return self.audio


__all__ = ["Result"]
