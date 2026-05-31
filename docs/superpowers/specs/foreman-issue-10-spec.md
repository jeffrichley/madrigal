# Spec: add CONTRIBUTING.md with dev-loop quickstart (issue #10)

## Goal
Add `CONTRIBUTING.md` at the repo root so a new contributor can clone
`jeffrichley/voice`, install deps, and pass `just check` using only the new
doc. Closes [#10](https://github.com/jeffrichley/voice/issues/10).

## Acceptance criteria
- `CONTRIBUTING.md` exists at repo root.
- Doc length is ~50 lines (hard ceiling: 70 lines including blank lines and
  headings) — issue calls out "no bloat".
- Doc contains, at minimum, sections covering: install (`uv sync
  --all-packages`), quality gate (`just check`), autofix (`just fix`),
  conventional commits (with allowed types + uppercase rule), branch
  naming, where design docs and plans live, and the pre-push hook.
- Install command matches what CI runs in `.github/workflows/ci.yml`
  (`uv sync --all-packages`), so a contributor following the doc gets the
  same environment as CI.
- Conventional-commit section lists every type allowed by
  `.github/workflows/pr-title-lint.yml` (feat, fix, chore, docs, refactor,
  test, style, build, ci, perf, revert) and the lowercase-subject rule.
- Pre-push section tells the contributor how to ACTIVATE the hook on a
  fresh clone (`git config core.hooksPath .githooks`) — the repo ships the
  hook script but does not auto-wire `core.hooksPath`, so a new contributor
  following only `git clone` would skip the gate without this step.
- Doc explicitly defers release process to `CLAUDE.md` and architectural
  context to `README.md` / `AGENTS.md` rather than restating them
  (matches the issue's out-of-scope list).
- `just check` passes after the change (the only file added is markdown, so
  this is a smoke gate, not a substantive one).

## Approach
The issue is a short documentation add. The right move is a single new
file at the repo root following the same compact, scannable tone as
`README.md` and `AGENTS.md` — bulleted lists, fenced code blocks for
commands, no marketing copy.

Source the content from files already in the repo so it stays in sync:

- **Install + quality gate + autofix:** copy command shape from `justfile`
  (`check: lint typecheck test`, `fix` recipe) and CI (`uv sync
  --all-packages` in `.github/workflows/ci.yml:34`). Use `--all-packages`
  rather than the bare `uv sync` mentioned in `CLAUDE.md` because CI uses
  the `--all-packages` form and the issue explicitly specifies it.
- **Conventional commits:** mirror the allowed-types list and lowercase-
  subject rule from `.github/workflows/pr-title-lint.yml:22-37` and
  `CLAUDE.md` "Conventions" section. Don't restate WHY — link to the
  workflow file for the source of truth.
- **Branch naming:** the observed pattern in `git log` is
  `<conventional-commit-type>/<kebab-case-description>` — examples in the
  recent history include `feat/parallel-gen`, `chore/rename-to-madrigal`,
  `chore/release-pipeline-pypi-publish`. Document this pattern with 2-3
  concrete examples; do not invent new rules.
- **Where docs live:** name both `docs/superpowers/specs/` (already
  populated with 3 design docs) and `docs/superpowers/plans/` (convention
  per the issue; directory will be created when the first plan lands). One
  sentence each.
- **Pre-push hook:** copy the bypass note from `CLAUDE.md` (`git push
  --no-verify`, use sparingly). ADD the hook-activation step (`git config
  core.hooksPath .githooks`) — this is the load-bearing line a new
  contributor needs because the repo doesn't auto-wire it, and forgetting
  it silently disables the gate.

Match the README's section-header tone (`## Develop`, `## Release`) and
keep prose tight. The doc is a quickstart, not a tutorial — assume the
reader has `uv`, `just`, and `git` already installed and link out to their
sites only if useful. No emojis (repo style).

## Sub-requests (topologically sorted)
1. Create `CONTRIBUTING.md` at the repo root with the seven sections
   listed in "File-level changes" below. Target ~50 lines, hard ceiling
   70.
2. Run `just check` to confirm the markdown add doesn't break the gate
   (it shouldn't — no Python or config files change).

## File-level changes
| Path | Change | Description |
| --- | --- | --- |
| `CONTRIBUTING.md` | CREATE | New file at repo root. Sections (in order): (1) intro — one sentence pointing at `README.md` for what madrigal is and `AGENTS.md` for agent conventions; (2) Install — `uv sync --all-packages`; (3) Quality gate — `just check` with one-line note on what it runs; (4) Autofix — `just fix`; (5) Commit conventions — allowed types list, lowercase-subject rule, link to `pr-title-lint.yml`; (6) Branch naming — `<type>/<kebab-description>` pattern with 2-3 examples from recent history; (7) Where docs live — `docs/superpowers/specs/` for design specs, `docs/superpowers/plans/` for implementation plans; (8) Pre-push gate — activation command (`git config core.hooksPath .githooks`), what it runs (`just check`), and the `--no-verify` bypass note. ~50 lines total. |

No other files change. No edits to `README.md`, `CLAUDE.md`, `AGENTS.md`,
`justfile`, or any workflow.

## Alternatives considered
- **Add a "Contributing" section to `README.md` instead of a separate
  file.** Rejected: the issue explicitly asks for `CONTRIBUTING.md` at the
  repo root, and GitHub surfaces that file in its contributor UI (the "New
  issue / Contributing guidelines" link) — a README section doesn't get
  the same treatment.
- **Generate the doc by transcluding `CLAUDE.md` "Working in this repo"
  section.** Rejected: `CLAUDE.md` mixes agent-facing constraints with
  human-facing dev-loop notes, and the issue's out-of-scope list (release
  process, architectural context) is exactly the stuff `CLAUDE.md`
  duplicates. A purpose-built file is cleaner than a transclusion that
  also pulls in the parts we want to exclude.
- **Skip the hook-activation step (`git config core.hooksPath
  .githooks`).** Rejected: without it, a fresh clone has no pre-push
  gate, and a contributor who follows the doc literally would believe the
  gate is running when it isn't. This is the kind of silent footgun
  CONTRIBUTING.md is supposed to prevent.
- **Do nothing (defer to CLAUDE.md + README.md).** Rejected: the issue is
  explicit that the dev-loop quickstart belongs in a standard file new
  contributors will look for; `CLAUDE.md` is agent-facing and `README.md`
  is product-facing.

## Open questions
None. The issue is concrete, the repo conventions are explicit in
`CLAUDE.md`, `AGENTS.md`, `justfile`, `pyproject.toml`, and the workflow
files, and the branch-naming pattern is observable from `git log`.

## Out of scope
- Release process — `CLAUDE.md` "Release" section owns this; CONTRIBUTING
  should link to it, not restate it.
- Architectural context (three-consumer design, parallel-gen, etc.) —
  `README.md` "Design" and `CLAUDE.md` "Design constraints" own this;
  CONTRIBUTING does not duplicate.
- Code-style rules beyond "ruff handles it" — ruff config in
  `pyproject.toml` is the source of truth; do not restate ruff selects /
  ignores.
- Editing `CLAUDE.md`, `AGENTS.md`, `README.md`, the justfile, or any
  workflow file.
- Creating `docs/superpowers/plans/` as a directory — mention it as a
  convention only; let it materialize when the first plan lands.
- Adding badges, contributor-covenant boilerplate, code-of-conduct, or
  PR/issue templates — none requested, all bloat per the "~50 lines" cap.
