# voice — feature list (full ambition + v0 carve-out)

> **For Jeff:** This is the WHAT, not the HOW. Full library ambition first, then named subsets for what ships at each version. Architecture decisions are encoded as open questions at the end so you can react.
>
> **Author:** Wren (draft) · **Reviewer:** Pepper (criterion-check) · **Decision:** Jeff
> **Date:** 2026-05-24

---

## 0. What voice is

A shared TTS substrate. Three named consumers today, all with equal first-class status:

- **Pepper conversational** (via `agent-core-voice` bus adapter): short utterances, low-latency, bytes-back, ephemeral.
- **Audiobook pipeline**: long-form batch with content-addressed cache, manifest, resume-after-crash, watermarking.
- **Chrona narration**: scene-shaped batch with character voices (mix/blend), eventual music-mix.

Voice is the pure library these three (and future consumers) share. No bus, no agent_core ties, no consumer-policy concerns.

---

## 1. Core capabilities (always-on across versions)

These are the always-true things voice provides at every version. Not "v0 features"; the bedrock the rest sits on.

- **Synthesize text → audio bytes** via a chosen voice.
- **Pluggable engine backends** (today Qwen3-TTS; tomorrow ElevenLabs / OpenAI / IndexTTS-2 / Higgs / Chatterbox). Single Protocol, swap implementations.
- **Named voice registry** (`voice_id` → reference audio + config). Voice creation = config + sample, not code.
- **Deterministic synthesis** with seed control. Same (model, voice, text, seed, params) → same audio.
- **Content-addressed cache** keyed on the determinism inputs. Survives across runs + projects.
- **Long-form chunking** (sentence / paragraph; pluggable for future custom strategies).
- **Cross-consumer-equal API**: no consumer's flow shape privileged over others'.
- **Error taxonomy** consumers can dispatch on (`EmptyText`, `TextTooLong`, `GPUOOM`, `VoiceNotPrepared`, etc.).
- **Public + MIT-licensed** so audiobook, Chrona, and Pepper-via-adapter consume on equal terms.

---

## 2. v0 — shipping today (Sunday, after sign-off)

The starter subset that proves the core capabilities work end-to-end.

- `voice.generate(text, spec) → Result` — single entry point, uniform return.
- `voice.speak(text, voice_id) → bytes` — convenience wrapper (most common shape).
- `voice.Spec` — request object: voice_id + chunk_strategy + cache + write_to + seed + extra + watermark (flag exists, no-op in v0) + parallel (flag exists, raises in v0).
- `voice.Result` — uniform response: audio + sample_rate + cache_key + cache_hit + path + manifest + timings (attribute population varies by Spec).
- **Engine backends:** `QwenTTSBackend` (lazy-imports qwen-tts + torch) and `FakeTTSBackend` (deterministic synthetic, no torch, for tests).
- **Voice registry:** YAML config file (`voices.yaml`), per-project location.
- **Cache:** filesystem hash store at `~/.cache/voice/`, minimal 6-field entry (audio, sha256, sample_rate, duration, generation_s, timestamp).
- **Chunking strategies:** `none` / `sentence` / `paragraph`. Simple registry dict.
- **Smoke tests** prove the apparatus.
- **Release apparatus already in place** (release-please + release.yml + qa-runner pattern available; ruleset). Per scaffold-agent-core-project skill, validated this morning.

v0 acceptance: a downstream consumer can `pip install voice`, register a voice, call `voice.speak(...)`, get bytes back. Audiobook can use it for batch with cache. Pepper can use it through the adapter for conversational.

---

## 3. v0.1 — Monday (the deferred-from-today work)

- **Parallel generation.** `Spec.parallel=True` actually works. List-input on `text=[...]` fans out across workers; `Result.audios` populates. The genuinely-novel piece: the engine-adapter-vs-worker-pool boundary question (does the adapter expose `synthesize_batch(texts)` or only single-shot + worker-pool wrapping?). Sub-spec Monday morning; implementation Monday afternoon.

---

## 4. v0.X+ — next-tier ambition (in scope; not next release)

Each here is roughly v0.2–v0.5 territory. Order is rough lean-on-priority, not committed.

- **Voice cloning workflow.** User provides reference audio → library trains/registers a new voice. Audiobook spec already tiers this: **Library** (pre-existing voice), **Designed** (parameterized), **Cloned** (from ref audio). Voice library exposes the full tier.
- **Voice direction / acting layer.** Prompt-driven emotion/style ("calm and slow," "excited"). Qwen3-TTS supports this via prompt; library exposes as `Spec.direction="calm and slow"` or similar.
- **Voice mixing / blending.** Combine voices in ratios (Pepper's voice is already 70/20/10 of three sources per the existing `VoiceInfo.blend` field). v0 carries the field through but doesn't expose mixing as a top-level operation; v0.X promotes blending to a first-class API.
- **Streaming generation.** For very long content, stream chunks as synthesized instead of buffering whole. Required for interactive conversational use at long-utterance scale.
- **Pluggable engines beyond Qwen3-TTS.** ElevenLabs adapter, OpenAI TTS adapter, IndexTTS-2, Higgs, Chatterbox. Each as a separate adapter conforming to the engine Protocol.
- **Multi-language voices.** Qwen3-TTS supports multiple languages; library exposes language-aware voice selection, or auto-detects from text.
- **Cross-engine voice equivalents.** Can `voice_id="pepper"` mean the same thing across Qwen / ElevenLabs / OpenAI, or is voice_id always engine-specific? Likely an architectural question (see §6).
- **Pronunciation override library.** Per-voice persistent dictionary so "Saki" pronounces a tricky proper noun the way Jeff says it should. Audiobook spec mentions this as a cached-resolutions store.
- **Voice safety guards.** Block named-person impersonation requests ("sound like Morgan Freeman"). Audiobook spec has a guard-LLM concept; library-level may be the right place.
- **Quality scoring / validation.** Automated quality check (MOS estimate, artifact detection) before delivering audio. Audiobook spec mentions threshold-based regen-on-fail.
- **Audio QA loop with regen-failed-segments.** If a segment fails QA, automatically retry with adjusted seed / params. Audiobook spec specifies 2-attempt ceiling.
- **Subtitle / timing export.** Audio + word-level timing for captioning. Audiobook needs this for SRT generation.
- **Real-time playback / interrupt.** For conversational use, allow consumer to interrupt mid-synthesis when user starts talking. Streaming + cancellation token.
- **Performance tuning + telemetry.** GPU-minutes per gen, throughput, cost projections. Already partially captured (`generation_s` per call); promote to first-class telemetry surface.
- **Watermark implementation.** Spec field is wired in v0; actual watermark generation algorithm lands here (EU AI Act Article 50 compliance for audiobook + Chrona public outputs).
- **Cache export / import.** Share a content-addressed cache across machines / between agents. "I generated chapter 1 on the desktop; pull it to the laptop." Audiobook + cross-machine work both want this.
- **A/B testing harness.** Same text, two voices, compare. Audiobook spec mentions this for narrator selection. Library-level support: `voice.compare(text, voices=[...])`.
- **Format support beyond WAV.** Today: WAV only. Future: MP3, FLAC, Opus, AAC. Audiobook wants FLAC; conversational streaming wants Opus; mobile wants AAC.
- **Sample rate selection.** Today: engine default. Future: `Spec.sample_rate_hz=22050` for audiobook quality, etc.
- **Voice versioning.** When "pepper v2" replaces "pepper v1" (re-recording, LoRA update), how does cache invalidate? Today: cache key includes model_id + params, so updating either invalidates. Future: explicit voice-version field in the registry.
- **Voice persona metadata.** Beyond voice_id: human-readable description, sample audio, typical use cases (for Pepper to ask "which voice fits this scene?"). Discoverability layer.
- **Deterministic seed catalog.** Knowledge that "for this voice, seed 17 always sounds best for emotional content" stored as voice-tagged metadata, not magic numbers in caller code.
- **Pluggable cache eviction strategies.** v0 cache grows monotonically; consumers wrap with their own logic if eviction is needed. Audiobook generates GB-scale audio over months; library-level eviction (LRU, size-cap, age-cap) will likely become a real demand within a year or two. Provide pluggable strategies then; until then, consumer-side wrapping is fine.

---

## 5. Out of scope (permanent — not planned even at v1.0)

These are things voice EXPLICITLY does not do, ever. Consumers either do them themselves or use a different tool.

- **CLI / standalone executable.** Voice is a library. The `voice` shell command does not exist; consumers wire one if they want.
- **GUI / web frontend.** Library only.
- **Audio post-processing** (EQ, compression, format conversion beyond what engines naturally produce). Consumer concern.
- **Real-time conversation orchestration.** Voice generates audio; the conversation loop (turn-taking, interrupt logic, ASR feedback) lives in `agent-core-voice` adapter or Pepper or Chrona.
- **Consent ledger / regulatory metadata storage.** Audiobook's manifest layer wraps voice.cache for this. Voice itself stays library-pure (no opinions on GDPR / EU AI Act / consent revocation policy).
- **Audio rendering for distribution.** Voice produces synthesis output. Mastering for podcast / audiobook distribution is downstream.
- **Multi-engine routing policy** (e.g., "use ElevenLabs for English, Qwen for Mandarin"). v0.X exposes per-call engine selection; the routing decision is consumer-layer.
- **Conversational state / dialogue management.** Voice synthesizes one utterance; conversation context lives in the consumer.

---

## 6. Open architectural questions for Jeff

Each of these is a one-line decision Jeff can react to. Naming them here so they don't get buried.

**6.1 — Voice catalog: per-project, per-workspace, or community?**

Today (v0): YAML file per project (`./voices.yaml`). Each consumer's project has its own. **(A) Stay per-project forever.** Simple, isolated, no cross-project surprises. **(B) Add per-workspace layer** at v0.X — `~/.config/voice/voices.yaml` provides shared voices that any consumer in this workspace can use, with per-project overrides. **(C) Add community / index layer** at v0.X+ — a published catalog of voices (with reference audio attached) that anyone can pull from, like a package registry. Most ambitious. Probably not v0 ever. **Recommendation:** start (A), name (B) as v0.X candidate, hold (C) for v1.0+ if real demand surfaces.

**6.2 — Voice cloning workflow: where does training live?**

Voice from cloned reference audio. **(A) Voice library does the training** (depends on training infrastructure — LoRA fine-tuning, GPU-required, hours-long). **(B) Voice library accepts pre-trained reference audio + voice_id** and a separate tool/script does the training (out of scope for voice itself). **(C) Voice library exposes a `clone_voice(name, ref_audio)` API** that delegates to whatever training service is configured.

**Recommendation:** **(B) for v0–v0.X**, then **(C) for v1.0+** if a workflow emerges where multiple consumers want clone-on-demand. Audiobook spec's three-tier model (Library / Designed / Cloned) maps naturally to (B): the library tier is registry-only; designed + cloned tiers have their own creation workflows that produce ref audio + register it.

**6.3 — Cross-engine voice equivalents: same voice_id across engines?**

Can `voice_id="pepper"` mean the same Pepper-voice whether the active engine is Qwen3-TTS, ElevenLabs, or OpenAI TTS? **(A) voice_id is engine-specific.** Each engine has its own voice catalog; switching engines = remapping voice_ids. **(B) voice_id is engine-agnostic; registry maps voice_id → per-engine config.** `voices.yaml` has a `pepper` entry that specifies engine-specific params for each engine that supports her. **(C) Voice library provides best-effort equivalency mapping** when a consumer requests `pepper` on an engine that doesn't have her configured (e.g., synthesize a near-match).

**Recommendation:** **(B) for v0–v1.0**. Engine-agnostic IDs at the API surface; per-engine details inside the registry entry. (C) is dangerous (silent voice substitution).

**6.4 — Voice safety guards: library-level or consumer-level?**

Audiobook spec has a guard-LLM concept that blocks named-person impersonation ("sound like Morgan Freeman"). **(A) Voice library has built-in guards** that refuse certain prompts/voices by default. **(B) Consumer-level** — voice library is policy-free; consumers add guards in their own layers. Audiobook turns guards on for public output; Pepper conversational doesn't because it's private.

**Recommendation:** **(B)**. Same shape as the cache-metadata split: voice is policy-free; consumers add the policy that fits their use. Audiobook's guard-LLM is an audiobook-layer concern.

**6.5 — Streaming generation in v0.X — push or pull model?**

When streaming-synthesis lands, do consumers **pull** chunks from a generator (`for chunk in voice.generate_stream(...)`) or **push** chunks to a callback (`voice.generate_stream(..., on_chunk=lambda audio: ...)`)?

**Recommendation:** **pull (generator) as the primary**; callback as a thin wrapper for consumers who prefer it. Pull is more Pythonic and composes better with async.

**6.6 — Telemetry: voice library tracks, or consumer reports?**

GPU-minutes, throughput, cost projections, error rates. **(A) Voice library aggregates telemetry internally** and exposes a `voice.stats()` surface. **(B) Voice library returns telemetry per-call** (already partly true — `Result.generation_s`); consumers aggregate.

**Recommendation:** **(B)**. Same library-purity principle. If aggregation becomes a real need, it's a v0.X consumer-side wrapper, not library-internal state.

---

## What this brief asks you for

Three sign-offs:

1. **v0 scope** (§2) — the subset that ships today.
2. **v0.1 deferral** (§3) — parallel-gen waits for Monday.
3. **Architectural answers** (§6) — your call on 6.1–6.6; we encode them in the implementation.

If §6 is too much to decide now, defaults are: 6.1 (A), 6.2 (B), 6.3 (B), 6.4 (B), 6.5 (pull), 6.6 (B). We can ship v0 on the defaults and revisit later.

Anything in §4 you want to elevate to v0.1? Anything you want stricken from the list entirely?
