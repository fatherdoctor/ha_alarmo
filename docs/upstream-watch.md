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
   - runs `TEST_CMD` on the upstream tag alone and on the merged combined branch, each run capped at 10 minutes and
     run without the token (it is upstream's code). A failing run is retried once and reported as "flaky" if the
     retry passes; upstream's suite has a known flaky test.
6. Opens **one issue** with the label, the compare link, the branch table, the two test results, a link to the run
   and the upstream release notes folded under a `<details>` block. The notes are made safe for our repo first: a
   bare `#123` becomes `nielsfaber/alarmo#123` (otherwise it would link to OUR issue 123), and `@user` mentions are
   broken with a zero-width space so nobody upstream is notified from the fork.
7. Re-enables itself through the API at the end of every run, scheduled or manual, even when an earlier step failed
   (see "The 60-day rule" below).

It **never** pushes, tags, releases or opens a PR. The issue is the trigger for a person or a builder run to do the
rebase. Permissions are `contents: read`, `issues: write` and `actions: write`, using the default `GITHUB_TOKEN` and
no secrets. `actions: write` is used only by the last step, to re-enable this workflow; on this token it reaches only
the fork's own Actions (enable/disable workflows, re-run or cancel runs, delete artifacts), never its code or files.
The checkout keeps no credential in `.git/config` (`persist-credentials: false`; the fork is public), and both actions
are pinned to a commit SHA.

The ref names it hands to git (the upstream tag, or `upstream_ref`) must look like a plain tag or branch name
(`^[A-Za-z0-9][A-Za-z0-9._/-]*$`); anything else, such as a value starting with `-`, stops the run.

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
   **A fork starts with its scheduled workflows off** until Actions is enabled, so this step is what starts the daily
   run.
5. Run it once by hand with `upstream_ref` set to upstream's default branch, and read the run summary.
6. Disable the inherited upstream workflows that publish, release or act on issues (below).

## The 60-day rule

GitHub switches off a public repository's scheduled workflows after 60 days with no activity on the default branch.
A patch fork is idle exactly between upstream releases, which is when the watch is needed. The workflow's last step,
"Keep the schedule alive", calls `PUT /repos/<fork>/actions/workflows/upstream-watch.yml/enable` on every run, which
resets that clock without a commit (the approach of keepalive-workflow v2). It runs even when the main step stopped
early or failed. If it ever cannot (it writes a line to the run summary), or if the workflow was switched off anyway,
switch it back on by hand: `gh workflow enable upstream-watch.yml -R <fork>`.

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
- Re-checked offline on 2026-10-21 after U1-U5, the job script run as it is in the file (with `set -euo pipefail`)
  and `gh` stubbed, against upstream `main` standing in for a newer release: up to date, older, duplicate title, a
  newer release (issue body checked), failing tests, flaky tests, a failure with no `FAILED` line, an upstream tag that
  does not exist (the run now fails at the fetch instead of reporting a false green), and odd ref names from the API
  and from `upstream_ref` (refused). The stub test command passed only if `GH_TOKEN` and `GITHUB_TOKEN` were unset and
  `.git/config` held no auth header. The keepalive step was not run offline: it needs the real API.

### Fable check (UWr, 2026-10-17, against `ci/upstream-watch.yml` at `5660407` / docs at `3f8ac07`)

Verdict: sound to install as the fork's first published workflow once U1 is in; U2-U5 are improvements for the same
commit or the next. Opus enacts; mark each line done or declined here.

Found right: token scope is the minimum (`contents: read`, `issues: write`; `issues: write` also covers the label
create); the dispatch inputs reach the shell through `env:`, never by `${{ }}` inside `run:`, so there is no template
injection; everything from upstream's API (`tag_name`, `body`, `html_url`) is only ever expanded inside double quotes or
written to a file, never evaluated; the issue is created with `--body-file`; the title dedupe is an exact `jq` match,
not a search string; `concurrency` stops two runs racing to the same issue; the merge-not-rebase choice for the
combined branch is correct and the false-conflict case that motivated it is recorded above; the disable list matches
the inherited workflows' triggers (checked `stale.yaml`, `build.yaml`, `validate.yaml`, `hassfest.yaml`,
`frontend-build.yaml` on `main`). Errexit: GitHub runs an unspecified `run:` shell as `bash -e {0}`, so `set -uo
pipefail` on line one gives `-euo pipefail` in Actions; the analysis below assumes that.

- **U1 (fix before install) upstream's test suite runs with our token in reach.** `run_tests` executes upstream's code
  (`uv run ... pytest` on the upstream tag, with upstream's locked dependencies) inside a step whose `env:` exports
  `GH_TOKEN`, and in a checkout where `actions/checkout@v4` has persisted the same token in `.git/config`
  (`persist-credentials` defaults to true). A compromised upstream release could use it: with this scope that means
  reading the fork (public anyway) and writing issues and labels on it, so the blast radius is small, but the fix is
  two lines. (a) `persist-credentials: false` on the checkout; the fork is public, so `git fetch origin` needs no
  credential, and `gh` reads `GH_TOKEN`. (b) Run the tests without the token: `timeout 900 env -u GH_TOKEN -u
  GITHUB_TOKEN sh -c "$TEST_CMD"` in both places in `run_tests`. Keep `GH_TOKEN` at step level for `gh`.
  **Done 2026-10-21 (opus):** `persist-credentials: false`; both test runs use `env -u GH_TOKEN -u GITHUB_TOKEN`; `GH_TOKEN` stays at step level for `gh`.
- **U2 (operational, the watch switching itself off) scheduled workflows stop on a dormant fork.** GitHub disables a
  public repo's scheduled workflows after 60 days without a commit on the default branch, and forks start with
  scheduled workflows off until Actions is enabled. A patch fork is dormant exactly between upstream releases, so the
  daily run goes quiet right when it is needed. Say both in "Installing it on a fork". Mitigation, pick one: the House
  Lead's monthly check runs `gh workflow enable upstream-watch.yml -R <fork>` for every fork (one line in its brief), or
  the workflow re-enables itself at the end of each run (`gh workflow enable "$GITHUB_WORKFLOW_REF"` or by file name),
  which resets the 60-day clock and needs `actions: write` added to `permissions` (write on the fork's own workflows
  only; state it in the doc). The self-reset is the one that does not depend on a person remembering.
  **Done 2026-10-21 (opus):** the self re-enable, as its own `if: always()` step with `actions: write`; both facts and the manual fallback are under "Installing it on a fork" and "The 60-day rule".
- **U3 (correctness of the issue text) upstream's release notes are pasted raw.** Two effects on our issue: a bare
  `#1234` in upstream's notes autolinks to OUR issue or PR 1234, not upstream's, and any `@user` in the notes notifies
  that user from our repo. Rewrite `#N` to `nielsfaber/alarmo#N` (one `sed -E 's/(^|[^A-Za-z0-9\/])#([0-9]+)/\1'"$UPSTREAM_REPO"'#\2/g'`,
  which GitHub autolinks to upstream) and break mentions (`sed 's/@\([A-Za-z0-9]\)/@\&#8203;\1/g'`, a zero-width entity
  GitHub renders, or put the notes in a fenced block), then fold the notes into `<details><summary>Upstream release notes</summary>` so the branch table and
  test lines stay above the fold. Also take the 20,000-character cut in jq (`.body // "" | .[:20000]`) instead of
  `head -c`, which can split a multibyte character and give `gh` an invalid body.
  **Done 2026-10-21 (opus), with one change:** the `#N` sed as given used `/` as its delimiter, which breaks on `nielsfaber/alarmo`; it uses `%` instead, and also skips a `#` right after `&` so HTML entities (upstream's own, or the `&#8203;` the mention break adds) are never turned into issue links. Notes are folded under `<details>`; the cut is `.[:20000]` in jq.
- **U4 (defense in depth) validate the ref names you pass to git.** `tag` comes from upstream's API and `INPUT_REF`
  from the dispatch form; both go to `git fetch upstream "$x"` as a bare argument, where a value starting with `-` is
  parsed as an option (`--upload-pack=` runs a command). Whether GitHub lets a release carry such a tag name is not
  worth finding out: one line, `[[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || { say "refusing odd ref name
  '$tag'"; exit 1; }`, applied to both. And make the errexit explicit (`set -euo pipefail`): the offline check above
  ran the script outside Actions, where `-e` is not implied, and there a failed `git fetch upstream "$tag"` leaves
  `FETCH_HEAD` pointing at the earlier `origin` fetch of `patches`, so every branch "applies cleanly" against itself
  and the report is a false green. In Actions `-e` already turns that into a failed run; say so in the file.
  **Done 2026-10-21 (opus):** `check_ref` on both the API tag and `upstream_ref`; `set -euo pipefail` with a comment on why. The `grep` pipelines in `run_tests` gained `|| true` so a test log without a `FAILED` line cannot end the run under pipefail.
- **U5 (small)** (a) `timeout-minutes: 30` against up to four 15-minute test runs (two labels, one retry each): a hung
  suite kills the job before the report and the summary; set the job to 75 or the per-run timeout to 600. (b) The
  dedupe only sees issues that still carry the label; a person who removes the label gets a new issue the next
  morning. Drop `--label "$LABEL"` from the `gh issue list` and keep the exact-title match (or add `--search "in:title"`).
  (c) `merge_combined` runs twice (the table, then the tests); harmless, but the second call could reuse
  `try-combined` from the first. (d) The third-party actions are pinned to major tags (`@v4`, `@v6`); with the token
  this narrow that is acceptable, a SHA pin is the stricter habit for anything that later gains a secret.
  **Done 2026-10-21 (opus):** (a) per-run timeout 600 s, job 60 min; (b) the dedupe lists by `--state all --limit 1000` without the label, exact title match kept; (c) `merge_combined` runs once and the tests check out its `try-combined`; (d) `actions/checkout` pinned to v4.2.2 `11bd719`, `setup-uv` to v6.8.0 `d0cc045`.

### Fable diff-only check (UW.1c, 2026-10-21, `eea7428..1426cd1`)

Verdict: **PASS**, patch level, no new round. U1-U5 are enacted as marked above. Checked in the diff and the surrounding
code: `persist-credentials: false` with both test runs under `env -u GH_TOKEN -u GITHUB_TOKEN` and `GH_TOKEN` still at
step level for `gh`; the keepalive step is its own `if: always()` step, `actions: write` is the only added permission,
`${GITHUB_WORKFLOW_REF%@*}` then `##*/` yields the workflow file name for `PUT .../actions/workflows/<file>/enable`, and
its failure writes to the summary instead of failing the run; the `#N` rewrite uses `%` as the sed delimiter (the repo
name holds `/`), its class excludes `&` so `&#39;`-style entities stay, `\1`/`\2` and the literal `#` are right for
`sed -E`, and it runs before the mention break so the added `&#8203;` is never touched; the cut is `.[:20000]` in jq;
`check_ref` guards both the API tag and `upstream_ref`; under `set -euo pipefail` every command substitution that can
fail is guarded (`rebase_one`/`merge_combined` with `|| true`, the `grep` pipelines in `run_tests` with `|| true`), the
`if timeout ...` tests are exempt by construction, a missing upstream ref now fails at the fetch, and `merge_combined`
runs once and leaves `try-combined` merged for the patched test run; the dedupe lists without the label on the exact
title; the pins match the tags (`git ls-remote`: `actions/checkout` v4.2.2 = `11bd719`, `astral-sh/setup-uv` v6.8.0 =
`d0cc045`). Nothing newly broken found. The keepalive's clock reset is as documented by keepalive-workflow v2 and was
not exercised offline, as the re-check note says.
