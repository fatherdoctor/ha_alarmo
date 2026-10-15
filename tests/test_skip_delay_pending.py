# ha_alarmo fork (Apache-2.0 section 4b), patch "skip-delay-refuses-in-pending":
# new test file.
"""Test that alarmo.skip_delay refuses during the entry delay."""

from typing import Any

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.helpers import (
    advance_time,
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
EXIT_TIME = 10
ENTRY_TIME = 30


def _setup(hass: Any, entry_id: str):
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away"],
        armed_away_exit_time=EXIT_TIME,
        armed_away_entry_time=ENTRY_TIME,
    )
    door = SensorFactory.create_door_sensor(
        entity_id=DOOR, name="Front Door", area=AREA_ID, modes=["armed_away"]
    )
    return setup_alarmo_entry(hass, areas=[area], sensors=[door], entry_id=entry_id)


async def _settle(hass: Any) -> None:
    """Let a sensor change run through the sensor handler and the alarm entity."""
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _arm_away(hass: Any) -> None:
    hass.states.async_set(DOOR, "off")
    await _settle(hass)
    await hass.services.async_call(
        "alarmo",
        "arm",
        {"entity_id": ALARM_ENTITY, "code": CODE, "mode": "away"},
        blocking=True,
    )
    await _settle(hass)


async def _skip_delay(hass: Any) -> None:
    await hass.services.async_call(
        "alarmo", "skip_delay", {"entity_id": ALARM_ENTITY}, blocking=True
    )
    await _settle(hass)


async def _pending(hass: Any) -> None:
    await _arm_away(hass)
    await advance_time(hass, EXIT_TIME + 1)
    assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
    hass.states.async_set(DOOR, "on")
    await _settle(hass)
    assert_alarm_state(hass, ALARM_ENTITY, "pending")


@pytest.mark.asyncio
async def test_skip_delay_in_pending_refuses(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """skip_delay during the entry delay raises and does not trigger."""
    storage, entry = _setup(hass, "skip_pending")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _pending(hass)

        with pytest.raises(ServiceValidationError, match="alarm_trigger"):
            await _skip_delay(hass)
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")

        # the entry delay itself is untouched: it still ends in triggered
        await advance_time(hass, ENTRY_TIME + 1)
        assert_alarm_state(hass, ALARM_ENTITY, "triggered")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_alarm_trigger_is_the_explicit_path(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """alarm_control_panel.alarm_trigger still triggers at once during pending."""
    storage, entry = _setup(hass, "skip_pending_trigger")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _pending(hass)

        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_trigger",
            {"entity_id": ALARM_ENTITY, "code": CODE},
            blocking=True,
        )
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "triggered")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_skip_delay_while_arming_still_arms_now(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """skip_delay during the exit delay arms at once, as before."""
    storage, entry = _setup(hass, "skip_arming")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _arm_away(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "arming")

        await _skip_delay(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_skip_delay_when_disarmed_still_raises(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """skip_delay outside arming/pending raises HomeAssistantError, as before."""
    storage, entry = _setup(hass, "skip_disarmed")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match="must be in state 'arming'"):
            await _skip_delay(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "disarmed")
