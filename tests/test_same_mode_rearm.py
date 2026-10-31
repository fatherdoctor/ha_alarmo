# ha_alarmo fork (Apache-2.0 section 4b), combined branch "patches": new test file.
#   The "same-mode-rearm" patch was dropped in 1.10.19.2 (upstream #1386/#1388; the
#   "Allow open initially" option covers the need); these cases pin that the build
#   is back to upstream's behavior.
"""Test that the dropped same-mode re-arm is gone: upstream behavior, plus the event."""

from typing import Any

import pytest
from homeassistant.core import Event

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


@pytest.mark.asyncio
async def test_same_mode_arm_keeps_closed_door_bypassed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A bypassed door that is closed now stays bypassed on a same-mode arm."""
    storage, entry = _setup(hass, "dropped_same_mode")
    failed: list[Event] = []
    success: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", failed.append)
    hass.bus.async_listen("alarmo_command_success", success.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(BACK_DOOR, "on")
        hass.states.async_set(SIDE_DOOR, "off")
        await _settle(hass)
        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] == [
            BACK_DOOR
        ]
        hass.states.async_set(BACK_DOOR, "off")
        await _settle(hass)
        success.clear()
        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] == [
            BACK_DOOR
        ]
        # ignored, as upstream; failed-to-arm-every-refusal reports it
        assert [e.data["reason"] for e in failed] == ["already_armed"]
        assert success == []
        # the door is still bypassed: opening it does not start the entry delay
        hass.states.async_set(BACK_DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_unbypass_service_is_gone(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """alarmo.unbypass is not registered (dropped with the patch)."""
    storage, entry = _setup(hass, "dropped_unbypass", master=True)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.services.has_service("alarmo", "arm")
        assert not hass.services.has_service("alarmo", "unbypass")
        await cleanup_timers(hass)
