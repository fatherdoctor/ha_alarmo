# ha_alarmo fork (Apache-2.0 section 4b), patch "refuse-raises-error": new test file.
"""Test that a refused arm command raises instead of returning quietly."""

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
from custom_components.alarmo import const

ALARM_ENTITY = "alarm_control_panel.test_area_1"
DOOR = "binary_sensor.front_door"
AREA_ID = "area_1"
CODE = "1234"
EXIT_TIME = 10
ENTRY_TIME = 30


async def _setup(hass: Any, entry_id: str, entry_time: int = ENTRY_TIME) -> list:
    """Set up one area with a door sensor; return the failed_to_arm event list."""
    events: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", events.append)
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away", "armed_home"],
        armed_away_exit_time=EXIT_TIME,
        armed_away_entry_time=entry_time,
        armed_home_exit_time=EXIT_TIME,
        armed_home_entry_time=entry_time,
    )
    door = SensorFactory.create_door_sensor(
        entity_id=DOOR,
        name="Front Door",
        area=AREA_ID,
        modes=["armed_away", "armed_home"],
        use_exit_delay=True,
        use_entry_delay=True,
    )
    storage, entry = setup_alarmo_entry(
        hass, areas=[area], sensors=[door], entry_id=entry_id
    )
    return events, storage, entry


async def _settle(hass: Any) -> None:
    """Let a sensor change run through the sensor handler and the alarm entity."""
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _arm(hass: Any, mode: str = "away") -> None:
    await hass.services.async_call(
        "alarmo",
        "arm",
        {"entity_id": ALARM_ENTITY, "code": CODE, "mode": mode},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_arm_while_arming_raises(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """An arm command during the exit delay raises and leaves the countdown alone."""
    events, storage, entry = await _setup(hass, "refuse_arming")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        assert_alarm_state(hass, ALARM_ENTITY, "arming")

        with pytest.raises(ServiceValidationError, match="arming"):
            await _arm(hass, "home")
        await hass.async_block_till_done()

        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        assert len(events) == 1
        assert events[0].data["reason"] == "not_allowed"
        assert events[0].data["command"] == "arm_home"

        # the original countdown still completes
        await advance_time(hass, EXIT_TIME + 1)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_arm_while_pending_raises(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """An arm command during the entry delay raises; the entry delay runs on."""
    events, storage, entry = await _setup(hass, "refuse_pending")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        await advance_time(hass, EXIT_TIME + 1)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")

        with pytest.raises(ServiceValidationError, match="pending"):
            await _arm(hass, "away")
        await hass.async_block_till_done()

        assert_alarm_state(hass, ALARM_ENTITY, "pending")
        assert [e.data["reason"] for e in events] == ["not_allowed"]
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_arm_while_triggered_raises(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """An arm command while triggered raises; the alarm stays triggered."""
    events, storage, entry = await _setup(hass, "refuse_triggered", entry_time=0)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        await advance_time(hass, EXIT_TIME + 1)
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "triggered")

        with pytest.raises(ServiceValidationError, match="triggered"):
            await _arm(hass, "home")
        await hass.async_block_till_done()

        assert_alarm_state(hass, ALARM_ENTITY, "triggered")
        assert [e.data["reason"] for e in events] == ["not_allowed"]
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_core_alarm_service_raises_too(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """HA's own alarm_control_panel.alarm_arm_home surfaces the refusal as well."""
    _events, storage, entry = await _setup(hass, "refuse_core_service")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "alarm_control_panel",
                "alarm_arm_home",
                {"entity_id": ALARM_ENTITY, "code": CODE},
                blocking=True,
            )
        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_push_action_refusal_does_not_raise(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A push-notification arm action that is refused is logged, not raised."""
    events, storage, entry = await _setup(hass, "refuse_push")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "away")
        hass.bus.async_fire(const.PUSH_EVENT, {"action": const.EVENT_ACTION_ARM_HOME})
        await hass.async_block_till_done()

        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        assert [e.data["reason"] for e in events] == ["not_allowed"]
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_successful_arm_still_returns_normally(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """A valid arm from disarmed does not raise and fires no failure event."""
    events, storage, entry = await _setup(hass, "refuse_ok")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await hass.async_block_till_done()

        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        assert events == []
        await cleanup_timers(hass)
