# ha_alarmo fork (Apache-2.0 section 4b), combined branch "patches": new test file.
"""Test the behavior that exists only when all five patches are combined."""

from typing import Any

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import ServiceValidationError

from tests.helpers import (
    advance_time,
    cleanup_timers,
    assert_alarm_state,
    setup_alarmo_entry,
    patch_alarmo_integration_dependencies,
)
from tests.factories import AreaFactory, SensorFactory

ALARM_ENTITY = "alarm_control_panel.test_area_1"
DOOR = "binary_sensor.back_door"
AREA_ID = "area_1"
CODE = "1234"
EXIT_TIME = 10


def _setup(hass: Any, entry_id: str):
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away", "armed_home"],
        armed_away_exit_time=EXIT_TIME,
        armed_away_entry_time=30,
        armed_home_exit_time=EXIT_TIME,
        armed_home_entry_time=30,
    )
    door = SensorFactory.create_door_sensor(
        entity_id=DOOR,
        name="Back Door",
        area=AREA_ID,
        modes=["armed_away", "armed_home"],
        auto_bypass=True,
        auto_bypass_modes=["armed_away", "armed_home"],
    )
    storage, entry = setup_alarmo_entry(
        hass, areas=[area], sensors=[door], entry_id=entry_id
    )
    storage.config["mode_switch_instant"] = True
    return storage, entry


async def _settle(hass: Any) -> None:
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _call(hass: Any, service: str, **data: Any) -> None:
    await hass.services.async_call(
        "alarmo", service, {"entity_id": ALARM_ENTITY, **data}, blocking=True
    )
    await _settle(hass)


@pytest.mark.asyncio
async def test_combined_refusals_all_report(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """Walk one evening through every refusal path and check each one reports."""
    storage, entry = _setup(hass, "combined_walk")
    failed: list[Event] = []
    success: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", failed.append)
    hass.bus.async_listen("alarmo_command_success", success.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # unbypass while disarmed: raises and reports
        with pytest.raises(ServiceValidationError):
            await _call(hass, "unbypass")
        await _settle(hass)
        assert [(e.data["reason"], e.data["command"]) for e in failed] == [
            ("not_allowed", "unbypass")
        ]
        failed.clear()

        # arm away with the back door open: it is bypassed after the exit delay
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        await _call(hass, "arm", code=CODE, mode="away")
        # an arm during the countdown is refused loudly (patch 1)
        with pytest.raises(ServiceValidationError):
            await _call(hass, "arm", code=CODE, mode="home")
        await _settle(hass)
        await advance_time(hass, EXIT_TIME + 1)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        assert hass.states.get(ALARM_ENTITY).attributes["bypassed_sensors"] == [DOOR]
        assert [e.data["reason"] for e in failed] == ["not_allowed"]
        failed.clear()

        # same mode again with the door still open: unchanged, reported
        await _call(hass, "arm", code=CODE, mode="away")
        assert [e.data["reason"] for e in failed] == ["already_armed"]
        failed.clear()

        # door closed, same mode again: rejoined (patch 2), success event
        hass.states.async_set(DOOR, "off")
        await _settle(hass)
        success.clear()
        await _call(hass, "arm", code=CODE, mode="away")
        assert failed == []
        assert [e.data.get("rejoined") for e in success] == [[DOOR]]

        # mode switch is instant (patch 3) and the door stays live
        await _call(hass, "arm", code=CODE, mode="home")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")

        # skip_delay in the entry delay refuses (patch 4) and reports (patch 5)
        with pytest.raises(ServiceValidationError):
            await _call(hass, "skip_delay")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")
        assert [(e.data["reason"], e.data["command"]) for e in failed] == [
            ("not_allowed", "skip_delay")
        ]
        await cleanup_timers(hass)
