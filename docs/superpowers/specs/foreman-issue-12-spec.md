# Spec: add ARCHITECTURE.md describing madrigal package layout (issue #12)

## Goal

Add an `ARCHITECTURE.md` at the repo root that gives a new contributor a
navigable map of the madrigal package: what modules exist, what each one is
responsible for, the key abstractions, and how modules compose. This closes
the gap between `README.md` (user-facing API) and `CLAUDE.md` (working
conventions + design constraints): neither explains internal structure.

For issue #12.

## Acceptance criteria

- `ARCHITECTURE.md` exists at the repo root (sibling of `README.md`, `CLAUDE.md`,
  `AGENTS.md`, `CONTRIBUTING.md`).
- Contains a package-layout tree showing every file under
  `packages/madrigal/src/madrigal/`, each annotated with its single-line
  responsibility.
- Documents each of the seven top-level modules / subpackages
  (`spec`, `result`, `generate`, `chunking`, `cache`, `engine`, `registry`)
  and the two private helper modules (`_cache_key`, `_wav`) with a
  paragraph explaining what it owns and what it does not own.
- Documents the four public top-level abstractions: `Spec`, `Result`,
  `TTSBackend`, and `Cache`.
- Contains a "module dependency graph" section that enumerates which module
  imports which (directional: A → B means A imports from B). No cycles.
- Contains an "engine adapters" section listing the two concrete backends
  (`FakeTTSBackend`, `QwenTTSBackend`) and the `_batch_fallback` utility;
  explains when an adapter should use the fallback vs. override.
- Contains a "three consumers" note (≤ one paragraph) cross-referencing
  `CLAUDE.md` for the design constraints; does NOT re-state the constraints
  in full.
- Audience is new contributors who just cloned the repo; no assumed prior
  knowledge of the codebase.
- Uses the same terse, declarative, technical prose as `CLAUDE.md` and `AGENTS.md`:
  short headings, code fences for trees and code, bullets over prose paragraphs
  where lists scan better.
- `just check` still passes after the file is added. Markdown files do not
  affect ruff / mypy / pytest, but the Worker must verify rather than assume.

## Approach

No GoF pattern applies — this is straightforward new-file documentation.
`ARCHITECTURE.md` is the conventional name for in-repo structural overviews
(used by Go stdlib, CPython, many OSS libraries); placing it at the repo root
matches community expectation and makes it discoverable without navigation.

The content is derived entirely from reading the source: the module docstrings
already describe boundaries cleanly, and the `__init__.py` files make the
re-export surface explicit. The Worker must read the modules themselves (as
the Planner did) rather than guess at content.

Key editorial decisions (resolved by the Planner; the Worker must follow them):

1. **Underscore-prefixed modules are documented as private.** `_cache_key.py`
   and `_wav.py` are internal to `generate.py`; their responsibilities are
   described in the architecture doc but under a "private helpers" heading to
   signal they are not stable API.

2. **Engine adapter section is concrete.** Rather than "see the engine
   subpackage," the section names `FakeTTSBackend`, `QwenTTSBackend`,
   `_batch_fallback.default_batch_loop()` by name, since these are the points
   a contributor is most likely to extend.

3. **No repetition of CLAUDE.md design constraints.** The three-consumer
   constraint, the no-bus-dependency rule, and the cross-consumer-equal API
   contract live in `CLAUDE.md` and are NOT re-stated in full here. One
   cross-reference sentence in a "design constraints" sidebar is enough.

4. **Dependency graph is text, not a diagram.** ASCII diagrams bitrot;
   a bulleted directional list (A → B means "A imports from B") stays
   accurate at zero tooling cost and can be updated in-editor.

## Sub-requests (topologically sorted)

1. Create `ARCHITECTURE.md` at the repo root using exactly the structure and
   content specified in the fenced block below. The Worker may fix typos and
   polish sentence flow but must preserve all headings, the package tree
   annotation, every module's responsibility paragraph, the dependency list,
   and the adapter section.

   ````markdown
   # madrigal — architecture

   Internal package map for contributors. For user-facing API see `README.md`;
   for working conventions, design constraints, and release process see `CLAUDE.md`.

   ## Package layout

   ```
   packages/madrigal/src/madrigal/
   ├── __init__.py          # Public re-export surface (Spec, Result, Cache, Registry, generate, speak)
   ├── spec.py              # Spec — frozen dataclass representing one synthesis request
   ├── result.py            # Result — frozen dataclass representing one synthesis response
   ├── generate.py          # Orchestrator: generate() + speak() entry points + routing
   ├── chunking.py          # Text-splitting strategies (none / sentence / paragraph)
   ├── _cache_key.py        # (private) SHA-256 cache key derivation
   ├── _wav.py              # (private) WAV concat + sample-rate / duration helpers
   ├── cache/
   │   ├── __init__.py      # Re-exports Cache, CacheEntry
   │   └── store.py         # Filesystem-backed content-addressed cache
   ├── engine/
   │   ├── __init__.py      # Re-exports all engine symbols (Protocol, errors, backends)
   │   ├── protocol.py      # TTSBackend Protocol + VoiceInfo dataclass + error taxonomy
   │   ├── fake.py          # FakeTTSBackend — deterministic sine-wave backend for tests
   │   ├── qwen.py          # QwenTTSBackend — real Qwen3-TTS (lazy-imports torch)
   │   └── _batch_fallback.py  # default_batch_loop() for adapters without native batching
   └── registry/
       ├── __init__.py      # Re-exports Registry, default_lookup_paths
       └── tiered.py        # YAML-backed tiered voice catalog (local → project → global)
   ```

   ## Module responsibilities

   ### `spec.py` — `Spec`

   Frozen dataclass that represents one call to `generate()`. All fields are
   optional except `voice_id`; defaults select the conversational fast-path
   (`chunk_strategy="none"`, `parallel=False`, `cache=False`). Hashable
   (custom `__hash__` because `extra: dict` is unhashable by default) so
   `Spec` instances can be used as dict keys or set members. Does NOT derive
   cache keys — that is `_cache_key.py`'s job.

   Fields at a glance:

   | Field | Type | Purpose |
   |-------|------|---------|
   | `voice_id` | `str` | Name resolved against the voice registry |
   | `chunk_strategy` | `str` | `"none"` / `"sentence"` / `"paragraph"` |
   | `cache` | `bool` | Enable content-addressed cache lookup/store |
   | `parallel` | `bool` | Route through `synthesize_batch` |
   | `write_to` | `Path \| None` | Also write audio to this path |
   | `watermark` | `bool` | EU AI Act Article 50 opt-in (deferred to v0.X+) |
   | `seed` | `int` | Determinism knob (same inputs → same audio) |
   | `extra` | `dict` | Engine-specific params (model_id, sample_rate, etc.) |
   | `max_batch_size` | `int \| None` | GPU OOM guard for large batches |

   ### `result.py` — `Result`

   Frozen dataclass that `generate()` always returns. Which fields are
   populated depends on `Spec` configuration — see the population matrix
   below. `bytes(result)` is the conversational fast-path; it raises
   `ValueError` if `result.audio is None` (e.g., a parallel-batch result
   where only `result.audios` is populated).

   | Spec path | `audio` | `audios` | `manifest` | `parallel_used` |
   |-----------|---------|----------|------------|-----------------|
   | single text, no parallel | ✓ | — | — (or list if chunked) | `False` |
   | UC1 explicit batch | — | ✓ | ✓ if cache | `True` |
   | UC2 chunked-parallel | ✓ (concat) | — | ✓ if cache | `True` |

   ### `generate.py` — orchestrator

   The library's single entry point. `generate(text, spec, *, backend, ...)` branches
   on `(type(text), spec.parallel, spec.chunk_strategy)` and routes to one of
   three internal paths:

   - **v0 sequential** (`_generate_v0_sequential`): single-text or
     cache+chunking fallback. Sequential per-chunk synthesis, WAV concat.
   - **UC1 explicit batch** (`_generate_uc1_batch`): `text` is `list[str]`;
     calls `backend.synthesize_batch`; returns `Result.audios`.
   - **UC2 chunked-parallel** (`_generate_uc2_chunked_parallel`): `text` is
     `str`; splits via `chunking.chunk()`; calls `backend.synthesize_batch`;
     concatenates via `_wav.concat_wavs()`; returns `Result.audio`.

   `_batched_synth_with_cache` is the shared cache-partition-then-reassemble
   helper used by both UC1 and UC2. `_synthesize_batch_chunked` applies
   `max_batch_size` sub-batching. `speak()` is a convenience wrapper around
   `generate()` that returns `bytes` directly.

   `generate.py` owns key-derivation delegation (`_cache_key.cache_key`),
   `Cache` read/write, voice resolution via `Registry.get()`, and `write_to`
   file writes. It does NOT implement chunking, WAV manipulation, cache
   storage, or batch fallback — those are all delegated.

   ### `chunking.py`

   Three built-in text-splitting strategies keyed by name:

   - `"none"` — whole text as a single chunk (conversational default)
   - `"sentence"` — regex split on `[.!?]` followed by whitespace
   - `"paragraph"` — blank-line split

   Public surface: `chunk(text, strategy) -> list[str]` and
   `list_strategies() -> list[str]`. The orchestrator calls `chunk()` before
   dispatching to the synthesis path.

   Not ML-grade sentence detection; consumers needing stronger boundary
   detection should preprocess and pass `chunk_strategy="none"`.

   ### `_cache_key.py` (private)

   Derives a hex-encoded SHA-256 key for a single chunk synthesis from:
   `model_id | voice_id | text | seed | watermark | spec.extra`. Deliberately
   excludes behavior-only fields (`write_to`, `cache`, `parallel`,
   `chunk_strategy`) that do not affect what audio comes out. Private to
   `generate.py`; not part of the public API.

   ### `_wav.py` (private)

   Three WAV helpers used by `generate.py`:

   - `wav_sample_rate_hz(audio: bytes) -> int` — reads sample rate from a WAV blob.
   - `wav_duration_ms(audio: bytes) -> int` — reads duration in milliseconds.
   - `concat_wavs(wavs: list[bytes]) -> bytes` — concatenates N same-format WAV blobs
     into one. Raises `ValueError` on format mismatch; `WavDecodingError` on decode
     failure.

   Private; consumers needing WAV manipulation beyond this should use the
   stdlib `wave` module or `soundfile` directly.

   ### `cache/` — `Cache`, `CacheEntry`

   Filesystem-backed content-addressed cache. `Cache` is a class keyed by
   caller-supplied string keys; it does NOT derive keys. Each entry is two
   files in a two-level shard directory (`<root>/<key[:2]>/<key[2:]>.wav`
   and `.json`) to keep directory sizes sane at millions of entries. Writes
   are atomic (temp-file + `os.replace`). Default root:
   `~/.cache/madrigal/` (honors `$XDG_CACHE_HOME`). No eviction in v0;
   consumers add eviction via wrapper layers.

   `CacheEntry` holds: `audio`, `sha256`, `sample_rate_hz`, `duration_ms`,
   `generation_s`, `timestamp_utc`. Policy-shaped metadata (consent, cost
   accounting, etc.) lives in consumer layers, not here.

   ### `engine/` — backends + protocol

   See the [Engine adapters](#engine-adapters) section below.

   ### `registry/` — `Registry`

   YAML-backed tiered voice catalog. Lookup order (first hit wins):

   1. `./.madrigal/voices.yaml` (per-cwd local override)
   2. `./voices.yaml` (project root)
   3. `~/.config/madrigal/voices.yaml` (user global; honors `$XDG_CONFIG_HOME`)

   `Registry.get(voice_id)` returns a `VoiceInfo` (defined in
   `engine/protocol.py`). `VoiceInfo` carries `voice_id`, `ref_wav`, `ref_text`,
   and `blend`. The registry is optional in `generate()`; pass `registry=None`
   to skip voice validation.

   ## Engine adapters

   The seam between `generate()` and the TTS model is the `TTSBackend`
   Protocol defined in `engine/protocol.py`. Any class that implements
   `prepare_voice()`, `synthesize()`, and `synthesize_batch()` satisfies the
   Protocol (structural typing; no inheritance required).

   **`engine/protocol.py`** — defines:
   - `TTSBackend` (`@runtime_checkable Protocol`)
   - `VoiceInfo` (frozen dataclass; used by both `engine/` and `registry/`)
   - Error taxonomy: `VoiceError` (base), `EmptyTextError`, `TextTooLongError`,
     `GPUOOMError`, `VoiceNotPreparedError`, `WavDecodingError`

   **`engine/fake.py` — `FakeTTSBackend`**

   Deterministic synthetic-audio backend for tests. Returns a sine wave
   whose pitch and duration are functions of `(voice_id, text, seed)`.
   Same inputs always produce identical WAV bytes. Delegates
   `synthesize_batch()` to `default_batch_loop()` (no native batching).
   Never used in production.

   **`engine/qwen.py` — `QwenTTSBackend`**

   Real backend wrapping Qwen3-TTS. Lazy-imports `torch` and `qwen_tts`
   inside `__init__` so `import madrigal.engine` works without torch
   installed. `prepare_voice()` builds an ICL (in-context-learning) prompt
   once per voice; `synthesize()` is the per-utterance hot path.
   `synthesize_batch()` calls `model.generate_voice_clone(text=list_of_texts)`
   for a real GPU speedup (~5–10× over sequential). Per-item timing is
   approximated (total / N) because the model does not expose per-item wall
   time.

   Requires `qwen-tts` (not on PyPI; available as a wheel in agent_core
   releases) and `soundfile` for WAV encoding.

   **`engine/_batch_fallback.py` — `default_batch_loop()`**

   Utility for adapters that don't natively batch. Delegates to N sequential
   `synthesize()` calls. Usage: one line in `synthesize_batch()` — composition
   over inheritance, preserving the Protocol's structural-typing shape.

   Adapters that benefit from native batching (Qwen3-TTS, ElevenLabs via
   concurrent HTTP, etc.) should override `synthesize_batch()` with their
   engine-specific implementation instead.

   ## Module dependency graph

   `A → B` means module A imports from module B. All arrows flow from
   higher-level to lower-level modules; there are no cycles.

   - `__init__` → `generate`, `cache`, `registry`, `result`, `spec`
   - `generate` → `_cache_key`, `_wav`, `cache`, `chunking`,
     `engine/protocol`, `registry`, `result`, `spec`
   - `_cache_key` → `spec`
   - `_wav` → `engine/protocol`
   - `cache/__init__` → `cache/store`
   - `cache/store` → *(stdlib only)*
   - `engine/__init__` → `engine/protocol`, `engine/fake`, `engine/qwen`
   - `engine/fake` → `engine/_batch_fallback`, `engine/protocol`
   - `engine/qwen` → `engine/protocol`
   - `engine/_batch_fallback` → `engine/protocol`
   - `registry/__init__` → `registry/tiered`
   - `registry/tiered` → `engine/protocol`

   ## Design constraints

   madrigal serves three distinct consumer profiles (conversational,
   audiobook, narration) each with different latency, caching, and batching
   needs. The API design must serve all three as first-class consumers. See
   `CLAUDE.md` for the full constraint set, including the no-bus-dependency
   rule and the parallel-gen empirical findings.
   ````

2. Run `just check` from the repo root and confirm a clean pass. If lint,
   typecheck, or pytest flags anything (markdown files should not affect
   them), investigate and fix rather than silencing the gate.

## File-level changes

| File | Change |
|------|--------|
| `ARCHITECTURE.md` (NEW) | Add contributor architecture map per the content block in Sub-request 1. |

No other files are touched. No code changes. No edits to `README.md`,
`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, or any module source.

## Alternatives considered

- **Expand `CLAUDE.md` with an internal-layout section instead of a new
  file.** Rejected: `CLAUDE.md` already has a focused audience (AI agents +
  load-bearing design constraints). Adding a new-contributor architecture map
  there would blur that audience and push `CLAUDE.md` past a readable length.
  A separate file is cleaner and matches the existing separation of concerns
  across the doc set.
- **Add architecture content to `README.md`'s existing `## Design` section.**
  Rejected: `README.md` is user-facing (install, usage, release). Internal
  module layout is contributor-facing, not user-facing. Mixing them creates
  the wrong document for both audiences.
- **Generate the architecture doc automatically from docstrings (e.g.,
  `pdoc`, `mkdocs`).** Rejected: the issue asks for a narrative architecture
  doc, not auto-generated API reference. Auto-generated docs require tooling
  setup and don't produce the compositional "how modules relate" narrative
  the issue asks for. Simple markdown at the repo root has zero tooling
  dependency and no bitrot risk from build-step failures.

## Open questions

None. The issue scope is clear, all modules were read, and the content is
fully derivable from the source code.

## Out of scope

- User-facing API docs — live in `README.md` and module docstrings.
- Release process — covered in `CLAUDE.md`.
- Contributing workflow — covered in `CONTRIBUTING.md`.
- Design constraints (three-consumer model, no-bus rule) — covered in
  `CLAUDE.md`; the architecture doc cross-references but does not duplicate.
- Test-suite structure — outside the issue's scope for this ticket.
- Future module additions or API evolution — document what exists today.
- Any code changes, linter suppressions, or CI workflow modifications.
