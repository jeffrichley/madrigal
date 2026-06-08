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
