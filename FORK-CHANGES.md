# ha_alarmo: changes to upstream Alarmo

This branch (`patches`) is upstream [nielsfaber/alarmo](https://github.com/nielsfaber/alarmo) **main at c6bb13a** (v1.10.19 plus #1493 and #1508) plus the
four patches below, versioned `1.10.19.2` (upstream version + a fourth number). It is licensed like upstream, under the
Apache License 2.0 (see `LICENSE`). As section 4(b) of that license asks, every modified source file carries a change
note at the top; the JSON files (which cannot hold comments) are listed here.

Each patch is also its own branch, cut from `v1.10.19`, so that each one can be offered upstream separately.

| Branch | What changes | Files |
|---|---|---|
| `refuse-raises-error` | An arm command refused because the alarm is arming, pending or triggered (or not initialized, or the mode is not supported) raises `ServiceValidationError` after firing `alarmo_failed_to_arm`. Scripts stop (or continue with `continue_on_error`); the frontend shows the reason. MQTT commands and push actions catch it and only log. | `alarm_control_panel.py`, `mqtt.py`, `__init__.py` |
| `mode-switch-instant` | New general option `mode_switch_instant` (default **off**): a switch between two armed modes skips the exit delay, so the house is never unwatched during a mode change. Set through the config API (`POST /api/alarmo/config`); the panel has no toggle yet. | `alarm_control_panel.py`, `const.py`, `store.py`, `websockets.py` |
| `skip-delay-refuses-in-pending` | `alarmo.skip_delay` during the entry delay (pending) refuses with `ServiceValidationError` instead of triggering the alarm at once; `alarm_control_panel.alarm_trigger` is the explicit way to trigger. | `alarm_control_panel.py`, `translations/en.json` |
| `failed-to-arm-every-refusal` | An ignored same-mode arm fires `alarmo_failed_to_arm` with the new reason `already_armed`; a refused `skip_delay` fires reason `not_allowed`, command `skip_delay`. | `alarm_control_panel.py`, `const.py`, `event.py` |

`manifest.json` version is `1.10.19.2`.

**Dropped in 1.10.19.2: `same-mode-rearm`.** It made an arm for the mode the alarm is already in watch the bypassed
sensors that had closed since, and added the service `alarmo.unbypass`. Upstream declined the same idea (#1386, #1388),
and the house no longer needs it: Alarmo's own "Allow open initially" sensor option covers a door left open at arming.
The patch, `alarmo.unbypass` and its service, constant, translation and icon entries, and the `patches`-only unbypass
case are removed. An arm for the mode the alarm is already in is ignored as upstream does, and
`failed-to-arm-every-refusal` still reports it as `alarmo_failed_to_arm` with reason `already_armed`. As upstream, a
sensor bypassed at arming stays bypassed until disarm, also through a switch to another armed mode. The
`same-mode-rearm` branch is kept as history only; it is no longer one of the patch branches the upstream watch rebases.
`tests/test_same_mode_rearm.py` now pins the dropped behavior (a closed bypassed door stays bypassed; no `unbypass`
service).

Tests: each patch adds one file under `tests/` in upstream's style; `tests/test_patches_combined.py` walks the four
together. `uv run pytest tests` passes 152 tests on this branch (127 upstream + 25; `tests/test_review_cases.py` holds
the AF1ar review cases).

Dev checks (DEVELOPMENT.md: `uv run pre-commit run --all-files`, `uv run pytest tests`): every patch branch and this
branch pass on the files they touch; the only hook failure is upstream's own (ruff-format on two v1.10.19 test files).
Upstream issue drafts are kept privately by the owner.

Not changed: the domain (`alarmo`), the frontend bundle, the storage format (one new optional key,
`mode_switch_instant`, which upstream ignores), MQTT topics and payloads.

Updating to a new upstream release: re-apply the four branches on the new tag, rebuild `patches`, version
`<upstream>.1`.
