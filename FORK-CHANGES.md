# ha_alarmo: changes to upstream Alarmo

This branch (`patches`) is upstream [nielsfaber/alarmo](https://github.com/nielsfaber/alarmo) **v1.10.19** plus the
five patches below, versioned `1.10.19.1` (upstream version + a fourth number). It is licensed like upstream, under the
Apache License 2.0 (see `LICENSE`). As section 4(b) of that license asks, every modified source file carries a change
note at the top; the JSON files (which cannot hold comments) are listed here.

Each patch is also its own branch, cut from `v1.10.19`, so that each one can be offered upstream separately.

| Branch | What changes | Files |
|---|---|---|
| `refuse-raises-error` | An arm command refused because the alarm is arming, pending or triggered (or not initialized, or the mode is not supported) raises `ServiceValidationError` after firing `alarmo_failed_to_arm`. Scripts stop (or continue with `continue_on_error`); the frontend shows the reason. MQTT commands and push actions catch it and only log. | `alarm_control_panel.py`, `mqtt.py`, `__init__.py` |
| `same-mode-rearm` | An arm for the mode the alarm is already in re-checks the bypassed sensors: each one that is closed now is watched again; `alarmo_command_success` carries `rejoined`. New service `alarmo.unbypass` (optional `sensors`) does the same without an arm command and returns `{rejoined, still_bypassed}`; it refuses when the alarm is not armed. | `alarm_control_panel.py`, `sensors.py`, `const.py`, `services.yaml`, `translations/en.json`, `icons.json` |
| `mode-switch-instant` | New general option `mode_switch_instant` (default **off**): a switch between two armed modes skips the exit delay, so the house is never unwatched during a mode change. Set through the config API (`POST /api/alarmo/config`); the panel has no toggle yet. | `alarm_control_panel.py`, `const.py`, `store.py`, `websockets.py` |
| `skip-delay-refuses-in-pending` | `alarmo.skip_delay` during the entry delay (pending) refuses with `ServiceValidationError` instead of triggering the alarm at once; `alarm_control_panel.alarm_trigger` is the explicit way to trigger. | `alarm_control_panel.py`, `translations/en.json` |
| `failed-to-arm-every-refusal` | An ignored same-mode arm fires `alarmo_failed_to_arm` with the new reason `already_armed`; a refused `skip_delay` fires reason `not_allowed`, command `skip_delay`. | `alarm_control_panel.py`, `const.py`, `event.py` |

Only in `patches` (where the five meet): a refused `alarmo.unbypass` fires `not_allowed` (command `unbypass`), and a
same-mode arm whose bypassed sensors are all still open fires `already_armed`. `manifest.json` version is `1.10.19.1`.

Tests: each patch adds one file under `tests/` in upstream's style; `tests/test_patches_combined.py` walks all five
together. `uv run pytest tests` passes 139 tests on this branch (108 upstream + 31; `tests/test_review_cases.py` holds
the AF1ar review cases).

Dev checks (DEVELOPMENT.md: `uv run pre-commit run --all-files`, `uv run pytest tests`): every patch branch and this
branch pass on the files they touch; the only hook failure is upstream's own (ruff-format on two v1.10.19 test files).
Results and the draft upstream issues (not posted): `docs/upstream/alarmo-issues-draft.md`.

Not changed: the domain (`alarmo`), the frontend bundle, the storage format (one new optional key,
`mode_switch_instant`, which upstream ignores), MQTT topics and payloads.

Updating to a new upstream release: re-apply the five branches on the new tag, rebuild `patches`, version
`<upstream>.1`.
