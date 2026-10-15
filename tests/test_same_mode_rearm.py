# ha_alarmo fork (Apache-2.0 section 4b), patch "same-mode-rearm": new test file.
"""Test the same-mode re-arm and the alarmo.unbypass service."""

from typing import Any

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import ServiceValidationError

from tests.helpers import (
    cleanup_timers,
    assert_alarm_state,
    setup_alarmo_entry,
    patch_alarmo_integration_dependencies,
)
from tests.factories import AreaFactory, SensorFactory

ALARM_ENTITY = "alarm_control_panel.test_area_1"
MASTER_ENTITY = "alarm_control_panel.master"
BACK_DOOR = "binary_sensor.back_door"
SIDE_DOOR = "binary_sensor.side_door"
AREA_ID = "area_1"
CODE = "1234"


def _door(entity_id: str, name: str) -> dict:
    """Door that is bypassed automatically when open at an arm (home and away)."""
    return SensorFactory.create_door_sensor(
        entity_id=entity_id,
        name=name,
        area=AREA_ID,
        modes=["armed_away", "armed_home"],
        use_exit_delay=True,
        use_entry_delay=True,
        auto_bypass=True,
        auto_bypass_modes=["armed_away", "armed_home"],
    )


def _setup(hass: Any, entry_id: str, master: bool = False):
    """Set up one area that arms instantly in both modes, with two doors."""
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away", "armed_home"],
        armed_away_exit_time=0,
        armed_away_entry_time=30,
        armed_home_exit_time=0,
        armed_home_entry_time=30,
    )
    areas = [area]
    if master:
        # the master entity exists only with two or more areas
        areas.append(
            AreaFactory.create_area(
                area_id="area_2",
                name="Test Area 2",
                modes=["armed_away", "armed_home"],
                armed_away_exit_time=0,
                armed_home_exit_time=0,
            )
        )
    return setup_alarmo_entry(
        hass,
        areas=areas,
        sensors=[_door(BACK_DOOR, "Back Door"), _door(SIDE_DOOR, "Side Door")],
        entry_id=entry_id,
        master_enabled=master,
    )


async def _settle(hass: Any) -> None:
    """Let a sensor change run through the sensor handler and the alarm entity."""
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _arm(hass: Any, mode: str = "home", entity: str = ALARM_ENTITY) -> None:
    await hass.services.async_call(
        "alarmo",
        "arm",
        {"entity_id": entity, "code": CODE, "mode": mode},
        blocking=True,
    )
    await _settle(hass)


async def _start_armed_with_open_doors(hass: Any, doors: list[str]) -> list[Event]:
    """Arm home with the given doors open; return the command_success event list."""
    for door in (BACK_DOOR, SIDE_DOOR):
        hass.states.async_set(door, "on" if door in doors else "off")
    await _settle(hass)
    await _arm(hass, "home")
    assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
    bypassed = hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"]
    assert sorted(bypassed or []) == sorted(doors)
    events: list[Event] = []
    hass.bus.async_listen("alarmo_command_success", events.append)
    return events


@pytest.mark.asyncio
async def test_same_mode_arm_rejoins_closed_door(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """Closing a bypassed door and arming the same mode again watches the door."""
    storage, entry = _setup(hass, "rearm_rejoin")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        events = await _start_armed_with_open_doors(hass, [BACK_DOOR])

        hass.states.async_set(BACK_DOOR, "off")
        await _settle(hass)
        await _arm(hass, "home")

        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] is None
        assert len(events) == 1
        assert events[0].data["action"] == "arm"
        assert events[0].data["mode"] == "home"
        assert events[0].data["rejoined"] == [BACK_DOOR]

        # the rejoined door is live again: opening it starts the entry delay
        hass.states.async_set(BACK_DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_same_mode_arm_keeps_open_door_bypassed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A door that is still open stays bypassed; the command is ignored as before."""
    storage, entry = _setup(hass, "rearm_still_open")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        events = await _start_armed_with_open_doors(hass, [BACK_DOOR])

        await _arm(hass, "home")

        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] == [
            BACK_DOOR
        ]
        assert events == []
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_same_mode_arm_without_bypass_is_ignored(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """With nothing bypassed, a same-mode arm changes nothing (upstream behavior)."""
    storage, entry = _setup(hass, "rearm_nothing")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        events = await _start_armed_with_open_doors(hass, [])

        await _arm(hass, "home")

        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert events == []
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_unbypass_service_returns_what_changed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """alarmo.unbypass rejoins the closed door and reports the open one."""
    storage, entry = _setup(hass, "unbypass_response")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        events = await _start_armed_with_open_doors(hass, [BACK_DOOR, SIDE_DOOR])

        hass.states.async_set(BACK_DOOR, "off")
        await _settle(hass)
        response = await hass.services.async_call(
            "alarmo",
            "unbypass",
            {"entity_id": ALARM_ENTITY},
            blocking=True,
            return_response=True,
        )
        await _settle(hass)

        assert response[ALARM_ENTITY] == {
            "rejoined": [BACK_DOOR],
            "still_bypassed": [SIDE_DOOR],
        }
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] == [
            SIDE_DOOR
        ]
        # the service is not an arm command: no command_success event
        assert events == []

        hass.states.async_set(BACK_DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_unbypass_service_only_listed_sensors(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """With `sensors`, only those bypassed sensors are considered."""
    storage, entry = _setup(hass, "unbypass_filter")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _start_armed_with_open_doors(hass, [BACK_DOOR, SIDE_DOOR])

        hass.states.async_set(BACK_DOOR, "off")
        hass.states.async_set(SIDE_DOOR, "off")
        await _settle(hass)
        response = await hass.services.async_call(
            "alarmo",
            "unbypass",
            {"entity_id": ALARM_ENTITY, "sensors": [SIDE_DOOR]},
            blocking=True,
            return_response=True,
        )

        assert response[ALARM_ENTITY] == {
            "rejoined": [SIDE_DOOR],
            "still_bypassed": [BACK_DOOR],
        }
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_unbypass_service_refuses_when_disarmed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """alarmo.unbypass on a disarmed alarm raises."""
    storage, entry = _setup(hass, "unbypass_disarmed")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        with pytest.raises(ServiceValidationError, match="must be armed"):
            await hass.services.async_call(
                "alarmo",
                "unbypass",
                {"entity_id": ALARM_ENTITY},
                blocking=True,
            )
        assert_alarm_state(hass, ALARM_ENTITY, "disarmed")


@pytest.mark.asyncio
async def test_same_mode_arm_on_master_rejoins(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A same-mode arm on the master entity rejoins in its areas and refreshes it."""
    storage, entry = _setup(hass, "rearm_master", master=True)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(BACK_DOOR, "on")
        hass.states.async_set(SIDE_DOOR, "off")
        await _settle(hass)
        await _arm(hass, "home", MASTER_ENTITY)
        assert_alarm_state(hass, MASTER_ENTITY, "armed_home")
        assert hass.states.get(MASTER_ENTITY).attributes["bypassed_sensors"] == [
            BACK_DOOR
        ]

        hass.states.async_set(BACK_DOOR, "off")
        await _settle(hass)
        await _arm(hass, "home", MASTER_ENTITY)

        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] is None
        assert hass.states.get(MASTER_ENTITY).attributes["bypassed_sensors"] is None
        await cleanup_timers(hass)
