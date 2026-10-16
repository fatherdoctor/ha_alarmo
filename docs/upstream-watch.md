# Upstream watch (template for every fork)

David Allison, 2026-10-15: an upstream watch is "one we should implement for all forks". This fork (fatherdoctor/ha_alarmo,
a patch fork of nielsfaber/alarmo) is the first. This page is written so that the next fork can copy it.

## What it does

`.github/workflows/upstream-watch.yml` runs every day (11:17 UTC) and can also be started from the Actions tab
("Run workflow"). It:

1. Reads the version our combined branch is built on: the `version` in `VERSION_FILE` on `PATCHES_BRANCH`, cut to
   `BASE_PARTS` numbers (`1.10.19.1` -> `1.10.19`).
2. Reads the upstream repo's latest release (`/releases/latest`; pre-releases and drafts are ignored).
3. If the upstream release is not newer (compared with `sort -V`), it stops: **up to date**.
4. If an issue titled `Upstream <tag> released - rebase patches` already exists (open or closed, label `LABEL`), it
   stops. That gives one issue per release. Closing the issue does not make it come back.
5. Otherwise, all in the runner and never pushed:
   - rebases each branch in `PATCH_BRANCHES` onto the upstream tag and reports "applies cleanly" or the files that
     conflict;
   - merges the tag into `PATCHES_BRANCH`. The combined branch is built by merging the patch branches, so a plain
     rebase would flatten those merges and report conflicts that a real update would not have; the workflow
     merges instead.
   - runs `TEST_CMD` on the upstream tag alone and on the merged combined branch. A failing run is retried once and
     reported as "flaky" if the retry passes; upstream's suite has a known flaky test.
6. Opens **one issue** with the label, the upstream release notes, the compare link, the branch table, the two test
   results and a link to the run.

It **never** pushes, tags, releases or opens a PR. The issue is the trigger for a person or a builder run to do the
rebase. Permissions are `contents: read` and `issues: write`, using the default `GITHUB_TOKEN` and no secrets.

The manual run takes two inputs:

- `upstream_ref`: test against any upstream tag or branch (for example `main`) without waiting for a release. The
  result goes to the run summary only, and no issue is opened.
- `dry_run`: report in the run summary only, with no issue opened.

## Installing it on a fork

1. Copy `upstream-watch.yml` to `.github/workflows/` on the fork's **default branch**. GitHub runs scheduled
   workflows only from the default branch. Add it as its own commit, and keep it out of any branch meant for an
   upstream PR.
2. Edit only the `env:` block:

   | Key | ha_alarmo value | Meaning |
   |---|---|---|
   | `UPSTREAM_REPO` | `nielsfaber/alarmo` | owner/repo of the upstream |
   | `TAG_PREFIX` | `v` | the text before the version in upstream's tags |
   | `PATCHES_BRANCH` | `patches` | the combined branch; its version file names our base |
   | `VERSION_FILE` | `custom_components/alarmo/manifest.json` | a JSON file with a `version` field |
   | `BASE_PARTS` | `3` | how many numbers of our version are upstream's (`1.10.19.1` -> 3) |
   | `PATCH_BRANCHES` | the five patch branches | space-separated, each rebased alone |
   | `TEST_CMD` | `uv run --frozen pytest -q -p no:cacheprovider tests` | upstream's own test command |
   | `LABEL` | `upstream-release` | created on the first run if it is missing |

3. Turn on **Issues** for the fork (forks start with Issues off): `gh repo edit <fork> --enable-issues`.
4. Turn on Actions for the fork if GitHub asks (Actions tab > "I understand my workflows, go ahead and enable them").
5. Run it once by hand with `upstream_ref` set to upstream's default branch, and read the run summary.
6. Disable the inherited upstream workflows that publish, release or act on issues (below).

## The workflows ha_alarmo inherited from upstream

| Workflow | Triggers | What it does | On our fork |
|---|---|---|---|
| `stale.yaml` "Close stale issues/pull requests" | daily + manual | labels and closes issues and PRs after 60 + 14 days | **Disable**: it would close our own upstream-release issues |
| `build.yaml` | release published | zips the component and uploads it to the release | **Disable**: we never release from the fork; a stray release would publish a zip |
| `validate.yaml` | push, PR, daily, manual | HACS validation, pytest, ruff | Keep on push/PR (it checks our patch branches). Its daily schedule only re-tests an unchanged tree, so disabling it is fine too |
| `hassfest.yaml` | push, PR, daily | Home Assistant manifest check | Keep (cheap, and it checks the patch branches) |
| `frontend-build.yaml` | push/PR touching the frontend, manual | lints and builds the frontend | Keep (it does not commit anything) |

Coordinator: `gh workflow disable stale.yaml -R fatherdoctor/ha_alarmo` and `gh workflow disable build.yaml -R fatherdoctor/ha_alarmo`.

## Notes

- Adding the workflow commit to `main` means the fork's `main` is no longer identical to upstream's. GitHub's
  "Sync fork" then merges instead of fast-forwarding. That is expected; keep the commit small and on its own.
- The cloud builder sessions cannot push `.github/workflows/` because their token has no workflow scope. The file is
  parked at `ci/upstream-watch.yml` on `main` until the Coordinator moves it with `git mv`. That file is not used
  where it is parked.
- Checked offline on 2026-10-16 by running the job script locally with `gh` stubbed, against upstream `main`, which is
  one frontend-only commit past v1.10.19. The cases checked were up to date, older, duplicate issue, a newer
  release, failing tests and flaky tests. The first draft rebased the combined branch, and it
  reported a false conflict in `alarm_control_panel.py`. That false conflict is why the combined branch is now
  merged instead. The real test command on that run: upstream `main` alone 108 passed; with `patches` merged in, 134
  passed.
