# Draft upstream issues for nielsfaber/alarmo

Status (2026-10-29): **1 POSTED as [nielsfaber/alarmo#1509](https://github.com/nielsfaber/alarmo/issues/1509)** by the
owner, with HA 2026.10.2, the skip_delay precedent and a continue_on_error line added (text below is what was posted).
**2 RETIRED - do not post:** the maintainer declined un-bypassing twice -
[#1386](https://github.com/nielsfaber/alarmo/issues/1386) ("I dont want to offer functions for un-bypassing sensors",
closed not planned 2026-03-30) and PR [#1388](https://github.com/nielsfaber/alarmo/pull/1388) (bypass is for a faulty
sensor, "standard practice that a sensor will remain bypassed until the next arming cycle"; no manual un-bypass
either). His suggested alternative, the sensor option "Allow open initially", covers the use case without a patch;
the owner's house is moving to it. `same-mode-rearm` stays on the fork only. Next to post: 5 (without its
already_armed half depending on 2 - it stands alone), then 4, then 3. 3, 4 and 5 unchanged since DRAFT v2 (2026-10-16).
Before any PR: rebase the branch onto upstream main (it moved: #1493 changed mqtt.py, #1508) and rerun the tests.
Nothing is posted until the owner decides; the owner posts.

## What worked upstream (8 issue -> merged PR pairs, 2025-11 to 2026-09)

Pairs studied: #1434/#1463, #1429/#1459, #1450/#1454, #1366/#1455, #1447/#1456, #1419/#1453, #1394/#1395,
#1383/#1393, plus #1345, #1310, #1306.

- Issues are short: 60-200 words, filed through the repo's templates. Bug form: Alarmo Version, HA Version,
  Bug description, Steps to reproduce, Relevant log output (often left empty). Feature template: Proposal,
  Additional info ("Your feature requests should be kept small").
- Plain first person, observed vs expected, no backstory. Good feature requests give one concrete use case and
  a specific ask.
- Fixes came from contributors, never the maintainer, as a PR of 40-125 words: Description, Fix, "Fixes #n".
  Small scoped fixes merged in hours or days.
- Pushback came on intent and security (a delay cap cut from 1 h to 5 min, unknown->open ignored "by design",
  "allow open initially" called possible misuse). All of those still merged after a revision. Our five
  tighten security rather than weaken it, which helps, but expect the "is this intended?" question on 2 and 4.
- PR #1306 already tried to fix the flaky test we hit, and it is still flaky. Issue 6 now says so.

Post one issue per patch, no umbrella, one or two at a time: 1 (posted), 5, 4, 3 (2 retired). When the maintainer is open to
it, open the PR with "Fixes #n" in the Description / Fix shape (example at the end).

Before posting:
- The fork is public, so the branch links work.
- Tick the template checklist honestly: search open and closed issues first, and be on the latest release.
- Fill in `<HA version>`.

Dev checks (AF1b, unchanged): every patch branch and `patches` pass upstream's pre-commit hooks on the files
they touch and `uv run pytest tests` (114/115/113/112/111/134; stock 108). The ruff-format hook fails only on
two stock v1.10.19 test files, which we left alone.

---

## 1. Bug form - POSTED as #1509 (2026-10-29)

Title: Refused arm command returns normally, so scripts carry on

~~~~
Alarmo Version: v1.10.19
HA Version: 2026.10.2

Bug description:
When an arm is refused because the area is pending, arming or triggered, Alarmo logs a warning and fires
alarmo_failed_to_arm, but the service call itself succeeds. A script carries on as if the arm worked and the
UI shows nothing. I'd expect a ServiceValidationError, as alarmo.skip_delay already raises when it's refused.
Scripts that should carry on anyway can set continue_on_error.

I have a fix with tests (raise after the event; the MQTT and notification-action handlers catch it and only
log) and can open a PR: https://github.com/fatherdoctor/ha_alarmo/tree/refuse-raises-error

Steps to reproduce:
1. Arm away with an entry delay on a door sensor.
2. Open the door so the alarm goes to pending.
3. Run a script that calls alarm_control_panel.alarm_arm_home, then creates a persistent notification.
4. The notification is created and the trace shows the arm step succeeded. The alarm is still pending.

Relevant log output:
Cannot go to state armed_home from state pending.
~~~~

## 2. Feature request - RETIRED (declined upstream as #1386 / #1388; see the status above)

Title: Re-arming the same mode should re-watch bypassed sensors that have closed

~~~~
Proposal
If a sensor is auto-bypassed at arming and closes later, there's no way to get it watched again except
disarming and re-arming. Arming the same mode again is ignored ("Alarm is already set to armed_away, ignoring
command.").

Proposal: on a same-mode arm, re-check the bypassed sensors and watch any that are closed now. Still-open
sensors stay bypassed; with nothing to re-watch the command is ignored as today. Optionally also an
alarmo.unbypass service that does the same without an arm command.

Additional info
Typical case: leaving with the garage door still open and closing it remotely ten minutes later. It stays
unwatched until the next disarm. I have both parts working with tests and can PR either one:
https://github.com/fatherdoctor/ha_alarmo/tree/same-mode-rearm
~~~~

## 3. Feature request

Title: Option to switch between armed modes without the exit delay

~~~~
Proposal
Switching from armed_away to armed_home runs the new mode's exit delay as arming, and nothing triggers during
that time, although nobody is leaving. I'd like an option (default off) to skip the exit delay when going from
one armed mode to another. The new mode is checked right away; if a sensor blocks it, the previous mode stays.
Arming from disarmed is unchanged.

Additional info
Mode switches usually happen from inside (a keypad, a bedtime routine), and keypads and the card don't send
skip_delay. My patch does the backend and the config API option; there's no panel toggle yet.
https://github.com/fatherdoctor/ha_alarmo/tree/mode-switch-instant
~~~~

## 4. Feature request

Title: skip_delay during the entry delay triggers the alarm at once

~~~~
Proposal
alarmo.skip_delay while pending goes straight to triggered. I know the service description says it skips the
entry delay too, but a "skip countdown" button meant for leaving sets off the siren if someone presses it
while coming in. I'd like skip_delay to refuse with an error during pending and only skip exit delays.
alarm_control_panel.alarm_trigger already covers triggering immediately.

Additional info
Happy to make the old behavior an option instead if you'd rather keep it. Fix with tests:
https://github.com/fatherdoctor/ha_alarmo/tree/skip-delay-refuses-in-pending
~~~~

## 5. Bug form

Title: alarmo_failed_to_arm not fired for a same-mode arm or a refused skip_delay

~~~~
Alarmo Version: 1.10.19
HA Version: <HA version>

Bug description:
I report refused commands from an automation listening for alarmo_failed_to_arm. Two refusals never fire it:
an arm for the mode that's already active (debug log only), and skip_delay outside arming/pending (raises, no
event). Every other refusal fires one. I'd suggest a new reason already_armed for the first, and not_allowed
with command skip_delay for the second. Fix with tests:
https://github.com/fatherdoctor/ha_alarmo/tree/failed-to-arm-every-refusal

Steps to reproduce:
1. Listen for alarmo_failed_to_arm in Developer tools > Events.
2. Arm away, wait until armed, arm away again: no event.
3. While disarmed, call alarmo.skip_delay: an error in the UI, no event.

Relevant log output:
(none at default log level)
~~~~

## 6. Bug form (optional)

Title: test_ready_to_arm_modes_changed_event_on_sensor_state_change still flaky after #1306

~~~~
Alarmo Version: 1.10.19 (clean checkout, uv sync)
HA Version: 2025.10.2 (from uv.lock)

Bug description:
This test fails about 1 run in 10 for me: 6 of 60 runs of tests/test_ready_to_arm_events.py. It looks like a
late ready_to_arm_modes_changed event arrives after backend_events.clear(), so ready_events[-1] is not the
one after the door opened. Also, pre-commit's ruff-format reformats tests/test_automations.py and
tests/test_delay_on.py on a clean checkout.

Steps to reproduce:
for i in $(seq 60); do uv run pytest -q tests/test_ready_to_arm_events.py; done

Relevant log output:
AssertionError: armed_away should not be available when door is open
assert 'armed_away' not in ['armed_away', 'armed_home']
~~~~

---

## PR body shape, for when the maintainer agrees

~~~~
Description
<one or two sentences: what was wrong>

Fix
<one or two sentences: what changes>. Tests in tests/<file>.py.

Fixes #<n>
~~~~

Lines for the PR bodies (from the AF1ar review, 2026-10-18), added to the Fix part of the matching PR:

- Patch 2 (`same-mode-rearm`): "A rejoin re-dispatches the ARM event with delay 0, so with MQTT enabled the
  event topic publishes ARM_<MODE> again while already armed; alarmo_command_success carries `rejoined`. Happy
  to use a separate event instead if you prefer."
- Patch 4 (`skip-delay-refuses-in-pending`): "Only en.json's skip_delay description is updated; I left the
  other languages to your usual translation flow."
