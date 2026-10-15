# ha_alarmo fork (Apache-2.0 section 4b), patch "failed-to-arm-every-refusal":
# new test file.
"""Test that every refused or ignored command fires alarmo_failed_to_arm."""

from typing import Any

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import HomeAssistantError

from tests.helpers import (
    cleanup_timers,
    assert_alarm_state,
    setup_alarmo_entry,
    patch_alarmo_integration_dependencies,
)
from tests.factories import AreaFactory, SensorFactory

ALARM_ENTITY = "alarm_control_panel.test_area_1"
DOOR = "binary_sensor.front_door"
AREA_ID = "area_1"
CODE = "1234"


def _setup(hass: Any, entry_id: str):
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away", "armed_home"],
        armed_away_exit_time=0,
        armed_home_exit_time=0,
    )
    door = SensorFactory.create_door_sensor(
        entity_id=DOOR, name="Front Door", area=AREA_ID
    )
    return setup_alarmo_entry(hass, areas=[area], sensors=[door], entry_id=entry_id)


async def _arm(hass: Any, mode: str) -> None:
    await hass.services.async_call(
        "alarmo",
        "arm",
        {"entity_id": ALARM_ENTITY, "code": CODE, "mode": mode},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_same_mode_arm_fires_already_armed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """An arm for the mode the alarm is already in fires reason already_armed."""
    storage, entry = _setup(hass, "every_refusal_same_mode")
    events: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", events.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        assert events == []

        await _arm(hass, "away")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        assert len(events) == 1
        data = events[0].data
        assert data["reason"] == "already_armed"
        assert data["command"] == "arm_away"
        assert data["state"] == "armed_away"
        assert data["entity_id"] == ALARM_ENTITY
        assert data["area_id"] == AREA_ID
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_other_mode_arm_fires_nothing(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A real mode switch is not a refusal: no failed_to_arm event."""
    storage, entry = _setup(hass, "every_refusal_switch")
    events: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", events.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        assert events == []
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_refused_skip_delay_fires_not_allowed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """skip_delay outside a countdown raises as before and now also fires."""
    storage, entry = _setup(hass, "every_refusal_skip_delay")
    events: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", events.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "alarmo", "skip_delay", {"entity_id": ALARM_ENTITY}, blocking=True
            )
        await hass.async_block_till_done()

        assert len(events) == 1
        data = events[0].data
        assert data["reason"] == "not_allowed"
        assert data["command"] == "skip_delay"
        assert data["state"] == "disarmed"
        assert data["entity_id"] == ALARM_ENTITY
