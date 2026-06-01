"""Tests for the private WAV helpers in ``madrigal._wav``.

Covers the typed-error contract: each helper wraps ``wave.Error`` and
re-raises ``WavDecodingError`` with the original exception preserved via
``__cause__``. Happy-path round-trips lock in current behaviour, and the
``ValueError`` format-mismatch branch in ``concat_wavs`` is kept distinct
from decoding errors (precondition violation, not decode failure).
"""

from __future__ import annotations

import io
import struct
import wave

import pytest

from madrigal._wav import concat_wavs, wav_duration_ms, wav_sample_rate_hz
from madrigal.engine import WavDecodingError

MALFORMED_WAV = b"not a wav"


def _make_wav(
    *,
    channels: int = 1,
    sampwidth: int = 2,
    framerate: int = 16_000,
    n_frames: int = 1_600,
) -> bytes:
    """Build a small well-formed WAV blob for happy-path tests."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        # n_frames samples of silence (int16 zeros)
        w.writeframes(struct.pack("<" + "h" * n_frames * channels, *([0] * n_frames * channels)))
    return buf.getvalue()


# --- wav_sample_rate_hz ----------------------------------------------------


def test_wav_sample_rate_hz_happy_path() -> None:
    """Happy-path round-trip: helper returns the rate it was given."""
    blob = _make_wav(framerate=22_050)
    assert wav_sample_rate_hz(blob) == 22_050


def test_wav_sample_rate_hz_raises_typed_error_on_malformed() -> None:
    """Malformed WAV → WavDecodingError, with __cause__ preserved."""
    with pytest.raises(WavDecodingError) as excinfo:
        wav_sample_rate_hz(MALFORMED_WAV)
    assert isinstance(excinfo.value.__cause__, wave.Error)


# --- wav_duration_ms -------------------------------------------------------


def test_wav_duration_ms_happy_path() -> None:
    """1600 frames @ 16_000 Hz == 100 ms."""
    blob = _make_wav(framerate=16_000, n_frames=1_600)
    assert wav_duration_ms(blob) == 100


def test_wav_duration_ms_raises_typed_error_on_malformed() -> None:
    """Malformed WAV → WavDecodingError, with __cause__ preserved."""
    with pytest.raises(WavDecodingError) as excinfo:
        wav_duration_ms(MALFORMED_WAV)
    assert isinstance(excinfo.value.__cause__, wave.Error)


# --- concat_wavs -----------------------------------------------------------


def test_concat_wavs_happy_path_round_trip() -> None:
    """Concatenation of two matching blobs sums their frame counts."""
    a = _make_wav(framerate=16_000, n_frames=800)
    b = _make_wav(framerate=16_000, n_frames=800)
    out = concat_wavs([a, b])
    assert wav_duration_ms(out) == 100  # 1600 frames @ 16k Hz == 100 ms
    assert wav_sample_rate_hz(out) == 16_000


def test_concat_wavs_empty_returns_empty_bytes() -> None:
    assert concat_wavs([]) == b""


def test_concat_wavs_single_returns_unchanged() -> None:
    blob = _make_wav()
    assert concat_wavs([blob]) is blob


def test_concat_wavs_raises_typed_error_on_malformed() -> None:
    """Malformed WAV inside the list → WavDecodingError, __cause__ preserved.

    Need at least 2 elements to enter the decode loop (single-element path
    returns the input unchanged without decoding).
    """
    good = _make_wav()
    with pytest.raises(WavDecodingError) as excinfo:
        concat_wavs([good, MALFORMED_WAV])
    assert isinstance(excinfo.value.__cause__, wave.Error)


def test_concat_wavs_still_raises_value_error_on_format_mismatch() -> None:
    """Format-mismatch is a caller precondition violation, NOT a decode error.

    Must remain ``ValueError`` so consumers can keep their existing
    precondition-check ``except`` clauses; do not migrate this branch
    into the new typed taxonomy.
    """
    a = _make_wav(framerate=16_000)
    b = _make_wav(framerate=22_050)
    with pytest.raises(ValueError):
        concat_wavs([a, b])
