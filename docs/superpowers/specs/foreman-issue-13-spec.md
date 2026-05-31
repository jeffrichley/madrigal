# Spec: refactor `madrigal.generate` dispatcher polish (issue #13)

> Source issue: [jeffrichley/voice#13](https://github.com/jeffrichley/voice/issues/13) — "refactor: voice endpoint polish — extract method + hoist imports"

## Goal

Three small quality-of-life cleanups to the `madrigal.generate` module — the
de-facto "voice endpoint" of the library:

1. Shrink the `generate()` dispatcher by extracting its preflight checks into
   a named helper.
2. Audit lazy (in-function) imports across the library and hoist any whose
   lazy-load benefit is not load-bearing.
3. Add 2–3 short comments where post-refactor control flow is non-obvious.

No behavior changes. No public API renames. No new tests.

## Mapping the issue's "voice endpoint module" to actual code

The library has no file literally called `endpoint`. The public entry-point
the issue describes is `packages/madrigal/src/madrigal/generate.py` —
specifically the `generate()` function (lines 43–139), which is the
synthesis dispatcher. `speak()` is a thin convenience wrapper around it.
Treat `generate()` as "the endpoint handler" referenced in the issue.

## Acceptance criteria

- `generate()` in `packages/madrigal/src/madrigal/generate.py` is **under
  ~30 lines of body** (def line + closing return, excluding the docstring).
- The extracted preflight helper has a clear name (suggestion:
  `_validate_dispatch_spec`), an explicit signature with keyword-only args
  matching the surrounding style, and a one-paragraph docstring naming each
  check it performs.
- The public signatures of `generate()` and `speak()` are byte-for-byte
  unchanged.
- All existing tests pass (`just check` green). No tests are added,
  modified, or skipped.
- Every lazy import (an `import` statement inside a function body) in
  `packages/madrigal/src/madrigal/**` either:
  - **is hoisted** to module level if there is no env-gated lazy-load
    benefit, **or**
  - **stays lazy** and is annotated with a `# lazy: <one-line reason>`
    comment naming the env-gating constraint (e.g., optional dep not in
    pyproject.toml, optional dep gated by a heavier sibling).
- 2–3 short (≤2 line) comments are added at spots in the post-refactor
  module where control flow is non-obvious to a first-time reader. Existing
  numbered-step comments inside `generate()` are preserved or relocated
  into the helper as appropriate; the goal is net-clearer, not net-more.
- No public API renames; no behavior changes; no test additions.

## Approach

The dispatcher in `generate()` currently interleaves five preflight checks
(watermark guard, cache requirement, input-type/parallel validation, §5
cache+parallel mutual-exclusion check, voice resolution) with a small
routing decision (4 lines). Reading it requires the reader to mentally
separate "what makes this request valid" from "where it's going to run."
Extracting the validation block into a named helper named after its
contract (`_validate_dispatch_spec`) makes the dispatcher's intent — *route
the call* — obvious at a glance and isolates the consistency checks so a
future reviewer can audit them as one unit.

The extracted helper takes `text`, `spec`, and `cache` (it inspects all
three) and returns `None` (its job is to raise on invalid combinations).
Keep the existing numbered-step comments (#1 through #5) by relocating
them into the helper; the dispatcher loses them because, post-refactor,
it no longer interleaves preflight with routing. The voice-resolution
diagnostic (`registry.get(spec.voice_id)`) stays in `generate()` because it
needs the `registry` argument that the helper shouldn't take, and
positionally it sits between validation and dispatch — not inside either.

For the import audit: search every file under
`packages/madrigal/src/madrigal/` for `import` statements inside function
bodies. The known sites are `engine/qwen.py:51-52` (`torch`, `qwen_tts`)
and `engine/qwen.py:128, 199` (`soundfile`). All three are gated by the
module's "optional heavy deps" contract — see the `engine/qwen.py`
module docstring, the `madrigal/engine/__init__.py` docstring, and the
root `pyproject.toml`'s `[[tool.mypy.overrides]]` block listing `torch`,
`qwen_tts`, and `soundfile` under `ignore_missing_imports`. The contract
is: `import madrigal.engine` must work on a host with none of these
installed. Hoisting any of them to module level breaks that contract,
because `madrigal/engine/__init__.py` does `from madrigal.engine.qwen
import QwenTTSBackend` unconditionally. The likely outcome: **no
hoists**, plus a `# lazy: …` annotation on each of the remaining four
sites naming the optional-dep constraint. If the audit turns up an
unrelated lazy import elsewhere in the package that has no env-gating
reason, hoist it.

For the comments: after extraction, identify 2–3 spots where intent is
not obvious. Strong candidates:
- The `if len(chunks) == 1: return _generate_v0_sequential(...)` short-
  circuit inside `_generate_uc2_chunked_parallel` (the "1 chunk degenerates
  to single-text" behavior).
- The `audios_slots: list[bytes | None]` pattern + the type-narrowing
  loop in `_batched_synth_with_cache` (input-order preservation across
  cache hit/miss reassembly).
- The dispatcher itself after extraction — a one-line note above the
  routing branches summarizing "UC1 → batch; UC2 → chunked-parallel;
  else → v0 sequential".

This matches the repo's existing house style — the file already uses
numbered `# N.` comments inside `generate()` and dense paragraph-style
block comments above the §5 mutual-exclusion logic. Keep that voice.

## Sub-requests (topologically sorted)

1. In `packages/madrigal/src/madrigal/generate.py`, add a new private
   helper `_validate_dispatch_spec(*, text, spec, cache)` whose body is
   the current `generate()` lines 62–103 (watermark guard, cache
   requirement, input-type/parallel validation, §5 mutual-exclusion
   check), preserving the inline `# 1.` / `# 2.` / `# 3.` / `# 4.` step
   comments. Give it a docstring listing each check.
2. In `generate()`, replace lines 62–103 with a single call
   `_validate_dispatch_spec(text=text, spec=spec, cache=cache)`. Confirm
   the body (excluding docstring) is now under ~30 lines.
3. Audit every Python file under `packages/madrigal/src/madrigal/` for
   `import` / `from … import …` statements sitting inside a function or
   method body. For each, decide: hoistable (no env-gating reason) →
   hoist to module level; load-bearing → add `# lazy: <reason>` on the
   import line. Expected outcome for `engine/qwen.py`: all four sites
   stay lazy with `# lazy:` annotations citing the optional-dep
   contract.
4. Add 2–3 short (≤2 line) comments at non-obvious flow spots identified
   above. Do not bloat already-commented blocks; aim for net-clearer.
5. Run `just check`. Triage any failures as regressions to fix —
   refactor-only means tests must still pass without modification.

## File-level changes

| File | Change |
|---|---|
| `packages/madrigal/src/madrigal/generate.py` | Extract preflight checks from `generate()` into new private `_validate_dispatch_spec(*, text, spec, cache)` helper. `generate()` body shrinks to <30 lines. Add 1–2 of the 2–3 non-obvious-flow comments here. |
| `packages/madrigal/src/madrigal/engine/qwen.py` | Annotate each of the 4 lazy imports (lines 51, 52, 128, 199) with `# lazy: <reason>` citing the optional-dep contract. Do NOT hoist. |
| Any other `madrigal/**/*.py` flagged by the audit | If a lazy import without env-gating is found, hoist it. Expected: none. |

No new files. No deletions. No test changes. No public API surface
changes (`__all__` in `generate.py` stays `["generate", "speak"]`).

## Alternatives considered

- **Decompose `generate()` into a small class with methods.** Rejected:
  the repo's house style is functional with module-level private helpers
  (see `_generate_v0_sequential`, `_generate_uc1_batch`,
  `_batched_synth_with_cache`); introducing a class is a stylistic break
  the issue doesn't justify.
- **Target `_generate_v0_sequential` (80 lines) instead of `generate()`.**
  Rejected: that path is linear chunk-iteration code with no preflight to
  separate, and the issue explicitly says "endpoint handler" — the
  public-facing dispatcher, not an internal path.
- **Hoist `soundfile` in `engine/qwen.py` to module level.** Rejected:
  `soundfile` is listed in `pyproject.toml`'s `[[tool.mypy.overrides]]`
  with `ignore_missing_imports = true`, signaling it's an optional dep
  paired with the qwen install. Hoisting would break `import
  madrigal.engine` on hosts without soundfile installed — same constraint
  as `torch` and `qwen_tts`.
- **Add comments without extraction.** Rejected: does not satisfy the
  "<~30 line method" acceptance criterion in the issue.

## Open questions

- The phrase "build the synthesis spec" in the issue is interpreted here
  as the preflight/validation block that finalizes the dispatch-ready
  request. If the issue author meant something more literal (e.g., the
  `Spec(voice_id=voice_id, **spec_kwargs)` construction inside `speak()`,
  which is one line and not a method-size problem), the Reviewer should
  flag this before the Worker runs — the helper name and contract change.
- The audit may find that **no** lazy imports qualify for hoisting. That's
  an honest finding, not a failure of the spec; the deliverable in that
  case is the `# lazy:` annotations + the `generate()` extraction +
  comments. The Worker should report the audit result either way.

## Out of scope

- Renaming `generate`, `speak`, `Spec`, `Result`, or any other public
  symbol.
- Changing the behavior of any code path, including edge cases like the
  empty-batch shortcut in `_generate_uc1_batch` or the 1-chunk degeneracy
  in `_generate_uc2_chunked_parallel`.
- Adding, removing, or modifying tests. The refactor is gated on
  `just check` passing with the existing suite unchanged.
- Refactoring the engine adapters (`engine/qwen.py`, `engine/fake.py`)
  beyond the lazy-import annotations described in Sub-request 3.
- Touching `docs/superpowers/specs/`, `CHANGELOG.md`, or release plumbing.
- Adding type-checker hints, runtime checks, or logging beyond what
  already exists.
