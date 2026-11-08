# AGENTS.md

## What this is

ha_alarmo is a public patch fork of nielsfaber/alarmo, an alarm system integration for Home Assistant (HACS). Our
changes live on patch branches, merged into `patches`; `main` tracks upstream. Nothing here is tagged or released by us.

## Commands

Set up once: `uv sync` (needs `uv` 0.8+; it fetches the pinned Python 3.13).

- Test: `uv run pytest -q` - green is `N passed`.
- Lint: `uv run ruff check .` - prints `All checks passed!`.
- Frontend: sources are in `custom_components/alarmo/frontend/src`; see `DEVELOPMENT.md` for its build.
- A live alarm panel, the box or real sensors are never exercised from a cloud session.

## Layout

| Path | What is there |
|---|---|
| `custom_components/alarmo/` | the integration (Python) |
| `custom_components/alarmo/frontend/` | the panel and card sources (TypeScript) |
| `tests/` | pytest suite |
| `docs/upstream-watch.md` | how the daily upstream-watch workflow works |
| `.github/workflows/` | upstream's build and validation workflows, plus `upstream-watch.yml` |
| `DEVELOPMENT.md` | upstream's development guide |

## Rules

- Each change is its own branch off upstream's release tag; `patches` is built by merging them, never by hand edit.
- Work only on the patch branches the owner has named; no tag, no release, no upstream PR from a lane.
- US English in code, comments, docs and commit messages.
- A commit ends with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` and nothing else from Claude.
- No session link, `Claude-Session:` line or claude.ai/code URL in a commit message or PR body.
- A PR body is short: the behavior change, the validation run, decisions needed.
- Alarm, arming and code behavior is design only until the owner approves; add tests with every patch.
- Public code gets the other-model adversarial review before a release; findings are fixed or declined in writing.
- No real codes, PINs, tokens, addresses or entity names from a house in code, tests or fixtures.
- Upstream posts (issues, PRs) are made only by the owner, in the owner's voice.

## Release

Not released: nothing is tagged or published from this repo. A new upstream release opens an issue; rebase the
patch branches onto its tag as `docs/upstream-watch.md` describes.

## Do not touch

- `main` - it mirrors upstream; never commit to it directly.
- `LICENSE` - upstream's license.
- `.github/workflows/` - a cloud session token cannot push it; describe the change in the PR.
- `uv.lock` - change it only with `uv lock` after a dependency change.

## Read more

- `README.md` - what Alarmo does and how a person installs it.
- `DEVELOPMENT.md` - upstream's development setup and checks.
- `docs/upstream-watch.md` - the rebase routine for new upstream releases.
