# Draft upstream issues for nielsfaber/alarmo - NOT POSTED

Status: DRAFT. Nothing here has been posted. David decides which to post and when; posting comes after the
patches have run on staging and in the house (board rows AF1c and AF1). Written 2026-10-15 by the trip-week
builder (opus lane) from the five patch branches and stock v1.10.19 (`main` of this fork).

Upstream's DEVELOPMENT.md asks for an issue before a feature: "before starting on implementation of a new
feature you are advised to create an issue for discussing your plans." So each issue proposes the change and
offers a PR; none of them opens with a PR.

## Recommendation: one issue per patch, no umbrella

Post five separate issues (plus, optionally, the small test-flake report at the end). Reasons:

- The maintainer can accept, decline or reshape each one on its own; an umbrella would tie a clear bug fix
  (issue 1) to a debatable option (issue 3).
- Each patch is already its own branch cut from v1.10.19 with its own test file, so each issue maps to one
  possible PR.
- Issues 1, 4 and 5 touch the same idea (refusals should be visible). Each of those mentions the others in one
  line instead of an umbrella.

Suggested order, one or two at a time so the maintainer is not handed five at once: 1, then 5, then 2, then 4,
then 3.

| # | Branch | Kind | Configurable? |
|---|---|---|---|
| 1 | `refuse-raises-error` | bug fix | no |
| 2 | `same-mode-rearm` | behavior change (plus a new service) | no; the old behavior is kept when nothing changes |
| 3 | `mode-switch-instant` | behavior change, as an option | yes, default off |
| 4 | `skip-delay-refuses-in-pending` | bug fix in intent, but a behavior change against the current docs (see note) | could be; recommend not |
| 5 | `failed-to-arm-every-refusal` | bug fix (missing events) | no |

Note on 4: the board row lists it as a bug fix. Upstream's own service text says skip_delay will "Skip the
remainder of the exit/entry delay and proceed directly to the next state", so triggering from pending is
documented behavior. The draft therefore argues it as a safety change, not as a bug, and offers an option if
the maintainer wants to keep the old behavior available. David: say if you would rather present it as a bug.

## Before posting (checklist)

- The fork must be public, or the link lines point nowhere. GitHub's public repository search does not find `fatherdoctor/ha_alarmo` today, so treat it as private until checked.
  Alternative: drop the link line and offer the PR in words.
- Search upstream's open and closed issues for each title's key words (refused arm, already set, bypassed,
  skip_delay pending, failed_to_arm) and link or comment on a match instead of opening a duplicate.
- Re-run the reproduction on the newest upstream release if it is newer than v1.10.19 (the upstream-watch
  workflow, board row UW, will say when).
- Post as plain markdown: the bodies below have no bold, no styled headers and no AI framing on purpose. The
  outer `~~~~` fences are only for copying; leave them out.

## Dev-check results behind these drafts (AF1b, 2026-10-15)

Per DEVELOPMENT.md (`uv sync`, `uv run pre-commit run --all-files`, `uv run pytest tests`), run on each patch
branch and on `patches`, with upstream's pinned hooks (pre-commit-hooks v6.0.0, bandit 1.8.6, ruff 0.14.1):

| Branch | yaml/toml/json | bandit | ruff check | ruff format (our files) | pytest | Lines vs v1.10.19 |
|---|---|---|---|---|---|---|
| `main` (stock v1.10.19) | pass | pass | pass | fails on 2 upstream files | 108 pass | - |
| `refuse-raises-error` | pass | pass | pass | pass | 114 pass | +278 -38, 4 files |
| `same-mode-rearm` | pass | pass | pass | pass | 115 pass | +444 -4, 7 files |
| `mode-switch-instant` | pass | pass | pass | pass | 113 pass | +208, 5 files |
| `skip-delay-refuses-in-pending` | pass | pass | pass | pass | 112 pass | +162 -13, 3 files |
| `failed-to-arm-every-refusal` | pass | pass | pass | pass | 111 pass | +150, 4 files |
| `patches` | pass | pass | pass | pass | 134 pass | +1419 -53, 19 files |

No hook asked for a change in any file a patch touches, so no branch needed a commit and `patches` was not
rebuilt; the manifest stays `1.10.19.1`. The whole-repo ruff-format hook still reports "Failed" on every branch
because stock v1.10.19 has two unformatted test files (`tests/test_automations.py`, `tests/test_delay_on.py`;
4+12 lines of formatting). Those are upstream's, so the patch branches leave them alone (fixing them in a patch
PR would mix unrelated lines into it); a PR offered upstream will show that hook red for the same reason as
upstream's own main. `tests/test_ready_to_arm_events.py::test_ready_to_arm_modes_changed_event_on_sensor_state_change`
is flaky on stock v1.10.19 too (6 of 60 runs of that file failed on `main`, 3/60 on `same-mode-rearm`, 4/60 on
`patches`); see the optional issue 6.

---

## Issue 1 - refused arm is silent to the caller (bug)

Title: Arm command refused while arming/pending/triggered returns normally, so scripts and the UI never see the refusal

~~~~
I run Alarmo 1.10.19 and drive it mostly from scripts and automations. When an
arm command is refused because the area is in a state that cannot be armed from, the service call still
returns as if it worked.

What happens

async_handle_arm_request logs "Cannot go to state armed_away from state pending." (or "alarm is not
initialized yet" / "Mode ... is not supported"), fires alarmo_failed_to_arm with reason not_allowed and
returns False. Nothing is raised, so:

- a script that calls alarm_control_panel.alarm_arm_away (or alarmo.arm) carries on to its next step as if
  the house were arming;
- the frontend (more-info dialog, a tile card, the Alarmo card) shows no error at all.

Steps to reproduce on stock 1.10.19

1. One area with an entry delay (say 30 s) on a door sensor, armed away.
2. Open the door so the area goes to pending.
3. While pending, run a script:

   sequence:
     - action: alarm_control_panel.alarm_arm_home
       target:
         entity_id: alarm_control_panel.alarmo
     - action: persistent_notification.create
       data:
         message: "arm went through"

4. The notification is created and the trace shows the arm step as successful. The log has the warning; the
   alarm is still pending.

Why it matters

The only way a script learns that its arm did nothing is to listen for alarmo_failed_to_arm separately and
correlate it, or to check the state afterward. Home Assistant's convention for a refused service call is a
ServiceValidationError: the script stops (or continues on purpose with continue_on_error) and the UI shows the
message.

Proposed change

Keep everything Alarmo does today (the warning, the alarmo_failed_to_arm event with reason not_allowed) and
then raise ServiceValidationError with the same reason instead of returning False. The two internal callers
that have no user to report to, the MQTT command handler and the actionable-notification listener, catch it and
keep their current log-only behavior. Wrong code and open sensors are not changed by this.

Configurable? I don't think it needs to be. A caller that wants the old behavior adds continue_on_error: true.

I have this as a small patch with tests (6, in the style of the existing test suite):
https://github.com/fatherdoctor/ha_alarmo/tree/refuse-raises-error
Happy to open a PR if the approach is acceptable.

Related: two refusals do not fire alarmo_failed_to_arm at all; I opened that separately.
~~~~

## Issue 2 - a bypassed sensor that closes is never watched again until disarm (behavior change)

Title: Re-arming the same mode should re-check sensors that were auto-bypassed at arming time

~~~~
With auto_bypass on, a sensor that is open when the area arms is bypassed, which is what I want: the house
arms with the garage door open instead of refusing. The trouble is that the sensor stays bypassed for the whole
armed period, even after it closes, and there is no way to get it watched again short of disarming and arming
again.

What happens

1. Arm away (or home) with a door open and auto_bypass enabled for that sensor. The area arms and the door is
   listed in bypassed_sensors.
2. Close the door.
3. Arm the same mode again (alarm_arm_away again, or alarmo.arm with the same mode). Alarmo logs at debug
   level "Alarm is already set to armed_away, ignoring command." and nothing changes: the closed door is still
   bypassed and opening it does not trigger anything.

The only way to get it watched is to disarm and arm again, which means a disarmed gap, an exit delay, and
for many people entering a code.

Why it matters

The common case is leaving with something open (a garage door still closing, a window someone forgot) and
closing it a few minutes later, often remotely. Everything after that point is unwatched for that sensor
until the next disarm, usually many hours.

Proposed change

1. When an arm request is for the mode the area is already in and the area has bypassed sensors, check them:
   each one that is closed now is removed from bypassed_sensors and watched again (sensor listener rebuilt).
   alarmo_command_success fires with an extra field rejoined listing them. Sensors still open stay bypassed.
   With nothing bypassed, or nothing closed, the command is ignored exactly as today. On the master entity
   this runs for each area.
2. A new entity service alarmo.unbypass (optional sensors list) that does the same without an arm command.
   It refuses with ServiceValidationError when the alarm is not armed and returns {rejoined, still_bypassed}
   as a service response, so an automation can say what is now covered.

No storage or MQTT change. If you would rather have only one of the two (the same-mode re-arm or the new
service), either works on its own.

Configurable? I don't think so: the old behavior is unchanged whenever a same-mode arm has nothing to rejoin.

Patch with tests (7): https://github.com/fatherdoctor/ha_alarmo/tree/same-mode-rearm
~~~~

## Issue 3 - switching between armed modes leaves the house unwatched for the exit delay (option)

Title: Option to switch between armed modes without the exit delay (mode_switch_instant)

~~~~
Switching from armed_away to armed_home (or night to home in the morning) without skip_delay runs the full
exit delay of the new mode as arming. During arming no sensor triggers, so the house goes from fully armed to
not watched at all for the exit time, although nobody needs to leave.

Steps to reproduce on stock 1.10.19

1. armed_home has an exit time of 60 s (common when the same mode is also used when leaving).
2. While armed_away, call alarm_control_panel.alarm_arm_home.
3. The state is arming for 60 s. Opening a door that is active in both modes during that minute does
   nothing.

Why it matters

A mode switch is usually done from inside the house (a keypad, a bedtime routine, a phone). The exit delay is
there so people can get out; on a switch between two armed modes it only opens a gap. Users can pass
skip_delay, but the keypads, the Alarmo card and most voice assistants do not.

Proposed change

A new general option mode_switch_instant, default off so nothing changes for existing installs. When on, an
arm request from an armed state is handled as if skip_delay were set: the new mode's sensors are validated at
once; an open blocking sensor fails the switch and the previous mode stays (the existing arm-failure revert).
Arming from disarmed still uses the exit delay.

The option is stored with the general config and accepted by the config API (POST /api/alarmo/config
{"mode_switch_instant": true}). My patch does not add a toggle to the panel because I have not touched the
frontend; I can add one if you point me at where general options live in the frontend repo. Upstream
installs that do not have the key ignore it.

Configurable? Yes, that is the point; default off.

Patch with tests (5): https://github.com/fatherdoctor/ha_alarmo/tree/mode-switch-instant
~~~~

## Issue 4 - skip_delay during the entry delay triggers the alarm at once (behavior change)

Title: alarmo.skip_delay during pending triggers the siren immediately; refuse instead and leave alarm_trigger for that

~~~~
alarmo.skip_delay is described as skipping the remainder of the exit or entry delay. During the exit delay
that arms now, which is useful. During the entry delay it calls async_trigger(entry_delay=0), so the alarm
goes straight to triggered.

I know this matches the service description ("proceed directly to the next state"). I am raising it because
in practice skip_delay ends up on a button or in a script whose purpose is "stop the countdown" (skip the exit
wait), and the same button pressed by someone coming in during pending sets off
the siren at once. The name reads as a convenience, not as a trigger.

Steps to reproduce on stock 1.10.19

1. Area armed away, entry delay 30 s on the front door.
2. Open the front door: state pending.
3. Call alarmo.skip_delay on the entity: state triggered immediately.

Proposed change

During pending, skip_delay raises ServiceValidationError naming the explicit path:
alarm_control_panel.alarm_trigger already triggers at once for anyone who wants that. The entry delay itself
is untouched and still ends in triggered. Behavior while arming, and the HomeAssistantError in every other
state, are unchanged. The service description would say "exit delay" only.

Configurable? It could be (an option that restores trigger-on-skip during pending), but I'd suggest not:
alarm_trigger already covers that use and one fewer option is simpler. If you prefer to keep the current
behavior the default, an opt-in option is fine with me.

Patch with tests (4): https://github.com/fatherdoctor/ha_alarmo/tree/skip-delay-refuses-in-pending

Related: with this change the refused skip_delay should also fire alarmo_failed_to_arm, which is part of the
separate failed_to_arm issue.
~~~~

## Issue 5 - two refusals never fire alarmo_failed_to_arm (bug)

Title: alarmo_failed_to_arm is not fired for an ignored same-mode arm or a refused skip_delay

~~~~
I report refused commands from one automation that listens for alarmo_failed_to_arm. Two refusals never
reach it:

1. An arm for the mode the area is already in. Alarmo logs "Alarm is already set to armed_away, ignoring
   command." at debug level and returns; no event.
2. alarmo.skip_delay outside arming/pending. It raises HomeAssistantError, but no event fires, unlike every
   other refused command (not_allowed, open_sensors, invalid_code all fire one).

Steps to reproduce on stock 1.10.19

1. Listen for alarmo_failed_to_arm in Developer tools > Events.
2. Arm away, wait until armed, call alarm_arm_away again: no event.
3. While disarmed, call alarmo.skip_delay: an error in the UI, no event.

Why it matters

A user presses "arm away" on a keypad and nothing visibly happens, because it already was armed away; a
notification automation built on alarmo_failed_to_arm cannot tell them. Same for a skip_delay button pressed at
the wrong time.

Proposed change

- Ignored same-mode arm: fire alarmo_failed_to_arm with a new reason already_armed, plus state, command and
  context_id as the other reasons carry. Internally this is a new event (EVENT_COMMAND_IGNORED); MQTT does not
  publish it, so the MQTT event topic is unchanged.
- Refused skip_delay: fire reason not_allowed with command skip_delay before raising, like the other refused
  commands.

Existing reasons are unchanged. One thing for the release notes: an automation that treats every
alarmo_failed_to_arm as a failed arm should ignore reason already_armed.

Configurable? No; it is an extra reason value on an existing event.

Patch with tests (3): https://github.com/fatherdoctor/ha_alarmo/tree/failed-to-arm-every-refusal
~~~~

## Issue 6 (optional) - flaky test on stock v1.10.19

Title: test_ready_to_arm_modes_changed_event_on_sensor_state_change fails about 1 run in 10

~~~~
While running the test suite as described in DEVELOPMENT.md (uv sync, uv run pytest tests) on a clean
checkout of v1.10.19, tests/test_ready_to_arm_events.py::test_ready_to_arm_modes_changed_event_on_sensor_state_change
fails intermittently: 6 of 60 runs of that file on my machine (Linux, Python 3.11, the locked Home Assistant
2025.10.2).

    assert "armed_away" not in available_modes
    AssertionError: armed_away should not be available when door is open
    assert 'armed_away' not in ['armed_away', 'armed_home']

The test takes ready_events[-1] after opening the door, and in the failing runs the last
ready_to_arm_modes_changed event still lists armed_away. My guess is that an event from the earlier
"disarmed / door closed" step sometimes arrives after backend_events.clear() and after the door event, so the
latest event is not the one the test means. Checking that some event after the door opened lacks armed_away,
rather than the last one, would make it deterministic, but I have not dug further than that.

Separately, uv run pre-commit run --all-files on v1.10.19 reports ruff-format changes in
tests/test_automations.py and tests/test_delay_on.py (formatting only).
~~~~
