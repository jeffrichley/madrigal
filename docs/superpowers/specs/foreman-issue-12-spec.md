# Spec: add ARCHITECTURE.md describing madrigal package layout (issue #12)

## Goal

Close the contributor-onboarding gap between README (user-facing) and CLAUDE.md
(working conventions) by adding a single top-level `ARCHITECTURE.md` at the
repo root that maps the madrigal Python package — what modules exist, what each
is responsible for, and how they compose. Audience: a new contributor who just
cloned the repo and wants the lay of the land. Closes
[#12](https://github.com/jeffrichley/voice/issues/12).

## Acceptance criteria

- A new file `ARCHITECTURE.md` exists at the repo root (same directory as
  `README.md`, `CLAUDE.md`, `AGENTS.md`).
- The doc opens with a one-paragraph "what this file is / who it's for" framing
  and explicitly cross-links the README (user-facing), CLAUDE.md (working
  conventions / load-bearing design constraints), and AGENTS.md (agent
  conventions) so readers know which doc to use when.
- The doc contains a fenced source-tree diagram of
  `packages/madrigal/src/madrigal/` listing every existing module file
  (including the `engine/`, `cache/`, `registry/` subpackages and the
  underscore-prefixed private modules `_cache_key.py` and `_wav.py`).
- For every module/subpackage in the tree, the doc has a one-to-three-sentence
  responsibility summary that matches what's actually in the module's
  top-of-file docstring (no invented responsibilities).
- The doc names the four key abstractions that bound the module graph —
  `Spec` (request), `Result` (response), `TTSBackend` (engine seam),
  `Cache` / `CacheEntry` (storage seam) — and states which module each lives
  in by path.
- The doc contains a "how the modules compose" section that describes the
  call flow through `generate.py`'s three paths (v0 sequential, UC1 explicit
  batch, UC2 chunked-parallel) at a paragraph each, naming the specific
  private helpers (`_generate_v0_sequential`, `_generate_uc1_batch`,
  `_generate_uc2_chunked_parallel`, `_batched_synth_with_cache`,
  `_synthesize_batch_chunked`) the Worker can verify against the source.
- The doc has a short "where the tests live" pointer mapping
  `packages/madrigal/tests/` mirror-structure to the source layout.
- The doc explicitly states what is OUT of scope for this file (user API
  examples, release process, contributing workflow) and points to the
  authoritative doc for each.
- Conventional-commit PR title (`docs:` type, lowercase subject) — the repo's
  `pr-title-lint` workflow will reject anything else.
- `just check` passes (this is a docs-only change so no source-code impact is
  expected; the gate must still be clean).

## Approach

This is a docs-only PR adding a single new file. The right shape for
`ARCHITECTURE.md` is a contributor's map, not a design treatise — readers
should be able to skim it in under five minutes and know which file to open
for which subsystem.

The repo already has the canonical sources of truth for each section's
content; the architecture doc summarizes and links, it does not duplicate.
Specifically:

- The package layout list at the bottom of `packages/madrigal/README.md`
  (lines 7-12) is a good seed but is currently incomplete — it omits
  `generate.py`, `spec.py`, `result.py`, and the private `_cache_key.py` /
  `_wav.py` helpers. The new `ARCHITECTURE.md` must list everything, not
  just the subpackages.
- Each module's top-of-file docstring is the source of truth for that
  module's responsibility. The Worker should paraphrase the docstring, not
  re-imagine the design. Concretely:
  - `madrigal/__init__.py` — public API re-exports (the seam to consumers).
  - `madrigal/generate.py` — the orchestrator. Has three execution paths
    (v0 sequential, UC1 batch, UC2 chunked-parallel) plus the shared
    cache-partition helper `_batched_synth_with_cache`. This is the largest
    module (541 LOC) and the heart of the library.
  - `madrigal/spec.py` — frozen `Spec` dataclass (request object).
  - `madrigal/result.py` — frozen `Result` dataclass (response with
    attribute-population-by-config semantics).
  - `madrigal/chunking.py` — three closed strategies (`none`, `sentence`,
    `paragraph`) in a dict registry.
  - `madrigal/_cache_key.py` — private sha256 derivation over the
    output-affecting subset of `Spec`.
  - `madrigal/_wav.py` — private WAV read / concat helpers.
  - `madrigal/engine/protocol.py` — `TTSBackend` Protocol + error taxonomy
    (`VoiceError` and its subclasses) + `VoiceInfo` dataclass.
  - `madrigal/engine/fake.py` — deterministic synthetic backend for tests.
  - `madrigal/engine/qwen.py` — real Qwen3-TTS backend with lazy torch
    import.
  - `madrigal/engine/_batch_fallback.py` — `default_batch_loop()` helper
    for adapters that don't natively batch.
  - `madrigal/cache/store.py` — filesystem hash store + `CacheEntry`
    dataclass.
  - `madrigal/registry/tiered.py` — YAML-backed tiered voice registry
    (local → project → global, first-hit wins).

The "how the modules compose" section reflects what `generate.py` actually
does — the routing logic in `generate()` (lines 43-139) branches on
`(input type, spec.parallel, spec.chunk_strategy, spec.cache)`. The doc
should describe the three paths factually, with a small diagram or arrow
list pointing from `generate()` → routing decision → which private path
function → which engine method (`synthesize` vs `synthesize_batch`).

Tone matches the existing repo voice (CLAUDE.md, AGENTS.md, the spec docs in
`docs/superpowers/specs/`): direct, second-person where natural, no
inflated marketing prose. Code and path references in backticks. Lowercase
subjects on headings is not required — Markdown convention applies — but
sentence-case headings fit the existing in-repo specs (see
`docs/superpowers/specs/2026-05-25-voice-parallel-gen-design.md` for
reference).

## Sub-requests (topologically sorted)

1. Create `ARCHITECTURE.md` at the repo root (same directory as `README.md`).
2. Write a 1-paragraph framing section explaining the doc's purpose +
   audience + how it relates to README, CLAUDE.md, AGENTS.md.
3. Add a fenced source-tree diagram listing every file under
   `packages/madrigal/src/madrigal/` (see the file-level changes section
   below for the exact tree to render).
4. Add a "Module responsibilities" section with one subsection per
   module/subpackage; each subsection's content paraphrases the
   corresponding module's top-of-file docstring in 1-3 sentences.
5. Add a "Key abstractions" section naming `Spec`, `Result`, `TTSBackend`,
   `Cache` / `CacheEntry` with the path where each is defined.
6. Add a "How the modules compose" section describing the three execution
   paths in `generate.py` (v0 sequential, UC1, UC2) and the shared
   `_batched_synth_with_cache` partitioner.
7. Add a short "Where the tests live" pointer to
   `packages/madrigal/tests/` and note that the test tree mirrors the
   source tree.
8. Add an "Out of scope for this doc" closer pointing readers to
   `README.md` for usage, `CLAUDE.md` for release/working conventions, and
   the in-flight `CONTRIBUTING.md` (issue #10) for the contribution
   workflow.
9. Verify the doc by reading it through end-to-end and checking that every
   path and file name referenced exists in the worktree.
10. Run `just check` and confirm it passes (docs-only, but the gate is
    cheap and catches stray issues).

## File-level changes

| File | Change | Notes |
| ---- | ------ | ----- |
| `ARCHITECTURE.md` (new) | Create at repo root | Single new file; contents described in the Approach + Sub-requests sections. Aim for ~150-250 lines of markdown. |

No source files, tests, configs, or other docs are modified. The package
README (`packages/madrigal/README.md`) has a stale partial list of modules,
but updating it is **out of scope** for this issue — that would expand the
PR's surface and dilute the deliverable. Flag it as a follow-up if the
Worker notices it; do not change it in this PR.

The source-tree diagram to embed in `ARCHITECTURE.md` (Worker must verify
against the worktree before writing it in, in case files have moved):

```
packages/madrigal/src/madrigal/
├── __init__.py            # public API re-exports
├── generate.py            # orchestrator: generate() + speak()
├── spec.py                # Spec request dataclass
├── result.py              # Result response dataclass
├── chunking.py            # text-splitting strategies
├── _cache_key.py          # private: sha256 key derivation
├── _wav.py                # private: WAV read / concat helpers
├── engine/
│   ├── __init__.py
│   ├── protocol.py        # TTSBackend Protocol + error taxonomy + VoiceInfo
│   ├── fake.py            # FakeTTSBackend (deterministic, for tests)
│   ├── qwen.py            # QwenTTSBackend (real; lazy torch import)
│   └── _batch_fallback.py # default_batch_loop() helper
├── cache/
│   ├── __init__.py
│   └── store.py           # filesystem hash store + CacheEntry
└── registry/
    ├── __init__.py
    └── tiered.py          # tiered YAML voice registry
```

## Alternatives considered

- **Put architecture content into the existing `packages/madrigal/README.md`
  instead of a new top-level file.** Rejected: the issue explicitly asks for
  a top-level `ARCHITECTURE.md` because that's where new contributors look
  first, and the package README is one level deep + already user-quickstart
  shaped. A top-level doc also matches the convention used by larger Python
  projects (e.g., Django, requests).
- **Expand the architecture doc to also cover the test layout in depth,
  release apparatus details, and the agent-core-voice adapter's relation to
  madrigal.** Rejected: the issue's "Out of scope" explicitly excludes
  release process and contributing workflow, and the adapter relationship
  is already well-covered in README.md's "Extraction-trigger" section. Keep
  the doc tight; over-scoping dilutes the map.
- **Generate the architecture doc from module docstrings programmatically
  (e.g., via a `just gen-architecture` task).** Rejected: premature
  automation for a doc that will change rarely. A hand-written doc that
  the reviewer can read top-to-bottom is the right shape until the package
  layout starts churning fast enough to make manual upkeep painful.
- **Do nothing / leave it to docstrings.** Rejected: explicitly called out
  in the issue as the gap to close. Docstrings serve API users; an
  architecture map serves contributors who need the cross-module picture
  before they touch any single file.

## Open questions

None. The issue is unambiguous, the repo conventions are documented in
CLAUDE.md and AGENTS.md, and every module to be summarized has a
top-of-file docstring the Worker can paraphrase from.

## Out of scope

- **Updating `packages/madrigal/README.md`** to fix its stale partial list
  of modules — separate concern, separate PR if warranted. Flag as a
  follow-up; do not touch in this PR.
- **Documenting the public API surface** (usage examples, parameter
  reference, behavior matrix). Lives in `README.md` and in module
  docstrings; the architecture doc references them but does not duplicate.
- **Documenting the release process or working conventions.** Lives in
  `CLAUDE.md`; architecture doc links to it.
- **Documenting the contribution workflow.** Tracked under issue #10 as
  `CONTRIBUTING.md`; architecture doc links forward to it (state "see #10"
  if the file does not yet exist at PR time).
- **Adding diagrams beyond a plain-text source tree** (Mermaid, image
  files, etc.). v0 of the doc is text-only; if a real call-graph diagram
  becomes valuable later, that's a follow-up.
- **Changing any source code, tests, or configuration.** This is a
  docs-only PR.
