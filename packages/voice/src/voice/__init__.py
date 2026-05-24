"""voice — pluggable TTS engine library.

Pure library: no bus, no agent-core dependencies. Three named consumers
(conversational via agent-core-voice adapter, audiobook pipeline, narration)
each get first-class API support. See repo CLAUDE.md for design constraints
and `docs/superpowers/specs/2026-05-24-voice-plan.md` for the full plan.

Public API:
    voice.generate(text, spec) -> Result    # single entry point
    voice.speak(text, voice_id) -> bytes    # convenience wrapper
    voice.Spec                              # request object
    voice.Result                            # response object
    voice.Registry                          # voice catalog
    voice.Cache, voice.CacheEntry           # content-addressed cache
    voice.engine                            # engine adapter submodule
    voice.chunking                          # chunking strategies

Quick start:

    from voice import generate, Spec
    from voice.engine import FakeTTSBackend  # or QwenTTSBackend in prod
    from voice.registry import Registry

    backend = FakeTTSBackend()
    backend.prepare_voice("pepper", Path("ref.wav"), "Reference text.")
    result = generate("Hello, Jeff.", Spec(voice_id="pepper"), backend=backend)
    audio_bytes = bytes(result)
"""

from voice.cache import Cache, CacheEntry
from voice.generate import generate, speak
from voice.registry import Registry
from voice.result import Result
from voice.spec import Spec

__all__ = [
    "Cache",
    "CacheEntry",
    "Registry",
    "Result",
    "Spec",
    "generate",
    "speak",
]
