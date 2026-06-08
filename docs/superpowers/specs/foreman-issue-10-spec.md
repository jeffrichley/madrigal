# Spec: add CONTRIBUTING.md with dev-loop quickstart (issue #10)

## Goal

Add a `CONTRIBUTING.md` at the repo root that a fresh human contributor can
follow to clone the repo, install dependencies, run the quality gate, and
ship a properly-formatted commit. The doc is the missing entry-point: today
`README.md` is for library users, `CLAUDE.md`/`AGENTS.md` are for AI agents,
and there is nothing aimed at a first-time human contributor.

For issue #10. First dogfood ticket for the Foreman v1 walking skeleton.

## Acceptance criteria

- `CONTRIBUTING.md` exists at the repo root (sibling of `README.md`).
- File is roughly 50 lines (40–60 acceptable, judged by blank-lines-inclusive
  `wc -l`); no bloat.
- Covers exactly the seven items from the issue body, each in its own
  scannable section or bullet:
  1. Install: `uv sync --all-packages`
  2. Quality gate: `just check` (lint + typecheck + tests)
  3. Auto-fix: `just fix`
  4. Conventional-commit conventions, naming the enforcing workflow
     `.github/workflows/pr-title-lint.yml`, and listing the allowed types
     (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `build`,
     `ci`, `perf`, `revert`) plus the lowercase-subject rule.
  5. Branch naming pattern grounded in actual repo history:
     `<type>/<short-description>` for human contributors (examples:
     `feat/parallel-gen`, `chore/rename-to-madrigal`), with a note that
     `foreman/issue-<N>` is reserved for automation.
  6. Doc locations: `docs/superpowers/specs/` for design specs and
     `docs/superpowers/plans/` for implementation plans.
  7. Pre-push gate: `.githooks/pre-push` runs `just check`; emergency bypass
     `git push --no-verify`.
- Includes the one-time `git config core.hooksPath .githooks` setup step in
  the Setup section. Without this the pre-push hook never fires on a fresh
  clone (the hook lives outside the default `.git/hooks/` path and nothing
  in the repo auto-wires it), so the issue's "new contributor could clone
  the repo and pass `just check`" criterion silently misses the gate.
- Defers release process and design constraints to `CLAUDE.md` (one-line
  cross-reference), per the issue's explicit out-of-scope list.
- Uses the same terse, declarative voice as `README.md`, `CLAUDE.md`, and
  `AGENTS.md`: short headings, bullets, fenced code blocks for commands.
- `just check` still passes on the branch after the new file lands. No code
  changes, but ruff/mypy/pytest are workspace-scoped and a top-level
  markdown file should not affect them — verify, don't assume.

## Approach

CONTRIBUTING.md is GitHub's standard contributor entry-point — GitHub's
"New issue" and "New pull request" UIs link to it automatically when it
lives at the repo root. Add it there. Keep it narrow: dev-loop mechanics
only. The repo already has three orienting docs with non-overlapping
audiences — `README.md` (library users), `CLAUDE.md` (AI agents working in
the repo + load-bearing design constraints + release process), `AGENTS.md`
(AI-agent conventions). CONTRIBUTING.md fills the gap for human
first-time contributors and stays out of the territory the other three own.

For tooling commands and conventions, copy from the existing sources of
truth rather than re-deriving them: `justfile` defines `check`, `fix`,
`lint`, `typecheck`, `test`; `.github/workflows/pr-title-lint.yml` defines
the allowed commit types and lowercase-subject rule; `CLAUDE.md` and
`AGENTS.md` already state the pre-push gate and squash-merge policy. The
spec PR locks in the exact phrasing so the Worker doesn't have to re-judge.

Two real findings from investigating the repo that the doc must address:

1. **Pre-push hook activation.** `.githooks/pre-push` exists and is
   executable, but the repo does not set `core.hooksPath = .githooks` for
   the developer automatically — neither `justfile` nor any post-clone
   script does it. A fresh clone has the hook file on disk but git ignores
   it. CONTRIBUTING.md's Setup section must include the one-time
   `git config core.hooksPath .githooks` step, otherwise the acceptance
   criterion "new contributor could clone the repo and pass `just check`
   using only the new doc" is met for `just check` but the pre-push gate
   the doc advertises silently does nothing on their machine. Mentioning
   this is the minimum honest fix; whether to auto-wire it via
   `just bootstrap` is a separate feature outside this spec's scope.

2. **Branch naming pattern.** No doc currently codifies branch naming.
   Reading `git branch -a` shows two coherent patterns: human work uses
   `<type>/<short-desc>` (`feat/parallel-gen`, `chore/rename-to-madrigal`,
   `feat/parallel-gen`) and automation uses `foreman/issue-<N>`
   (`foreman/issue-12`, `foreman/issue-13`). The issue asks us to ground
   the pattern in "recent branches" — that's the pattern. CONTRIBUTING.md
   should document the human pattern and note that the `foreman/` prefix
   is reserved.

For the `docs/superpowers/plans/` directory: the issue explicitly asks us
to mention both `specs/` and `plans/`. `docs/superpowers/specs/` exists
with four files today; `docs/superpowers/plans/` does not yet exist. That
is fine — the directory will materialize when the first plan is written
(per the superpowers `writing-plans` convention), and documenting the
location ahead of time anchors the convention. Do NOT create an empty
`plans/` directory or a placeholder file; that's scope creep and adds noise.

## Sub-requests (topologically sorted)

1. Create `CONTRIBUTING.md` at the repo root using exactly the structure
   and content shown in the fenced block below. The Worker may polish
   wording (typos, sentence-flow) but must preserve the section headings,
   the commands, and the seven required topics.

   ````markdown
   # Contributing to madrigal

   Thanks for your interest. This doc covers the dev loop for human
   contributors. For deeper context see `CLAUDE.md` (release process,
   load-bearing design constraints) and `AGENTS.md` (AI-agent conventions).

   ## Prerequisites

   - Python 3.12 (matches `.python-version`)
   - [`uv`](https://docs.astral.sh/uv/) for dependency and workspace management
   - [`just`](https://github.com/casey/just) as the quality-gate runner

   ## Setup

   ```bash
   git clone https://github.com/jeffrichley/voice
   cd voice
   uv sync --all-packages
   git config core.hooksPath .githooks   # enable the pre-push gate
   ```

   ## Dev loop

   - `just check` — run the full quality gate (lint + typecheck + tests). Run before every push.
   - `just fix` — auto-apply ruff lint fixes and formatting.
   - `just lint` / `just typecheck` / `just test` — individual gates.

   The pre-push hook (`.githooks/pre-push`) runs `just check` automatically
   once you've configured `core.hooksPath` above. Emergency bypass:
   `git push --no-verify` — use sparingly.

   ## Branch naming

   Human contributors: `<type>/<short-description>` matching the conventional
   commit type. Examples: `feat/parallel-gen`, `fix/wav-error-chain`,
   `docs/contributing`. The `foreman/issue-<N>` prefix is reserved for
   automation.

   ## Commits and PRs

   - Conventional commits required; PR titles are linted by
     `.github/workflows/pr-title-lint.yml`.
   - Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`,
     `style`, `build`, `ci`, `perf`, `revert`.
   - Subject must NOT start with an uppercase letter.
   - The repo squash-merges; the PR description becomes the commit body —
     write it thoughtfully.

   ## Where docs live

   - `docs/superpowers/specs/` — design specs (one per non-trivial feature)
   - `docs/superpowers/plans/` — implementation plans

   For substantial features, land a spec doc before the implementation PR.
   The existing files in `docs/superpowers/specs/` are good models.
   ````

2. Run `just check` from the repo root and confirm a clean pass. If lint
   or typecheck flags anything (it shouldn't — only a root-level markdown
   file is added), do not silence the linter; investigate and fix.

3. Confirm the file is roughly 50 lines (`wc -l CONTRIBUTING.md`). 40–60
   is acceptable. If it grew significantly larger, trim content the issue
   marked out of scope rather than padding past 60.

## File-level changes

| File | Change |
|------|--------|
| `CONTRIBUTING.md` (NEW) | Add ~50-line dev-loop quickstart per the content block in Sub-request 1. |

No other files are touched. No code changes. No edits to `CLAUDE.md`,
`AGENTS.md`, `README.md`, `justfile`, or any workflow.

## Alternatives considered

- **Expand `README.md`'s existing `## Develop` section instead of adding a
  separate file.** Rejected: GitHub treats `CONTRIBUTING.md` as a special
  file (auto-linked from the New Issue / New PR UI), so a contributor doc
  there is materially more discoverable than a README section. The issue
  body also explicitly asks for `CONTRIBUTING.md`.
- **Auto-wire `core.hooksPath = .githooks` via a `just bootstrap` recipe so
  contributors don't have to remember the one-time setup step.** Rejected:
  out of scope for this issue (the ask is documentation, not new tooling).
  Worth a follow-up issue; flagged in Out of scope.
- **Duplicate the release-process and design-constraints sections from
  `CLAUDE.md` so CONTRIBUTING.md is fully self-contained.** Rejected: the
  issue body explicitly puts release process out of scope and architectural
  context out of scope. Duplication would also drift over time; a one-line
  cross-reference to `CLAUDE.md` is the right call.
- **Create an empty `docs/superpowers/plans/` directory (e.g. with a
  `.gitkeep`) so the path referenced in the doc actually exists.**
  Rejected: noise. The directory will materialize when the first plan is
  written, which is the superpowers convention. The doc references the
  location as the convention; that's enough.

## Open questions

None. The issue is unambiguous, the seven required topics map cleanly to
sections, and the two repo-grounded judgment calls (pre-push hook
activation and branch naming) were resolved by reading the repo.

## Out of scope

- Any contributor topic beyond the dev loop (architecture, release,
  benchmarking, deeper testing patterns) — defer to `CLAUDE.md` / `AGENTS.md`
  / `docs/superpowers/specs/`.
- Code-style nits — ruff handles them via `just fix` / `just lint`.
- Release process — already covered in `CLAUDE.md`.
- Architectural context and load-bearing design constraints — covered in
  `CLAUDE.md` and `AGENTS.md`.
- Creating an empty `docs/superpowers/plans/` directory or placeholder file.
- Auto-wiring `core.hooksPath = .githooks` via `just bootstrap` or a uv
  post-install hook. Worth a follow-up issue, but explicitly not part of
  the documentation ask.
- Editing `README.md`, `CLAUDE.md`, `AGENTS.md`, `justfile`, or any
  workflow file. CONTRIBUTING.md links out to the existing sources of
  truth; it does not modify them.
- Bumping `VERSION` or editing `CHANGELOG.md` — release-please derives
  those from the conventional-commit subject of the merged PR.
