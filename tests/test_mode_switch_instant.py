# ha_alarmo fork (Apache-2.0 section 4b), patch "mode-switch-instant": new test file.
"""Test the mode_switch_instant option (switch armed modes without exit delay)."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import Event

from tests.helpers import (
    advance_time,
    cleanup_timers,
    assert_alarm_state,
    setup_alarmo_entry,
    patch_alarmo_integration_dependencies,
)
from tests.factories import AreaFactory, SensorFactory
from custom_components.alarmo.store import AlarmoStorage

ALARM_ENTITY = "alarm_control_panel.test_area_1"
DOOR = "binary_sensor.front_door"
WINDOW = "binary_sensor.window"
AREA_ID = "area_1"
CODE = "1234"
EXIT_TIME = 30


def _setup(hass: Any, entry_id: str, instant: bool | None):
    """One area, exit delay in both modes; a door and a window watched in both."""
    area = AreaFactory.create_area(
        area_id=AREA_ID,
        modes=["armed_away", "armed_home"],
        armed_away_exit_time=EXIT_TIME,
        armed_away_entry_time=30,
        armed_home_exit_time=EXIT_TIME,
        armed_home_entry_time=30,
    )
    sensors = [
        SensorFactory.create_door_sensor(
            entity_id=DOOR,
            name="Front Door",
            area=AREA_ID,
            modes=["armed_away", "armed_home"],
        ),
        # a window watched only in home mode that blocks arming when open
        SensorFactory.create_window_sensor(
            entity_id=WINDOW,
            name="Window",
            area=AREA_ID,
            modes=["armed_home"],
            auto_bypass=False,
        ),
    ]
    storage, entry = setup_alarmo_entry(
        hass, areas=[area], sensors=sensors, entry_id=entry_id
    )
    if instant is not None:
        storage.config["mode_switch_instant"] = instant
    return storage, entry


async def _settle(hass: Any) -> None:
    """Let a sensor change run through the sensor handler and the alarm entity."""
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _arm(hass: Any, mode: str) -> None:
    await hass.services.async_call(
        "alarmo",
        "arm",
        {"entity_id": ALARM_ENTITY, "code": CODE, "mode": mode},
        blocking=True,
    )
    await _settle(hass)


async def _armed_away(hass: Any) -> None:
    hass.states.async_set(DOOR, "off")
    hass.states.async_set(WINDOW, "off")
    await _settle(hass)
    await _arm(hass, "away")
    await advance_time(hass, EXIT_TIME + 1)
    assert_alarm_state(hass, ALARM_ENTITY, "armed_away")


@pytest.mark.asyncio
async def test_mode_switch_uses_exit_delay_by_default(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """Without the option a mode switch runs the exit delay (upstream behavior)."""
    storage, entry = _setup(hass, "switch_default", instant=None)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _armed_away(hass)

        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        await advance_time(hass, EXIT_TIME + 1)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_mode_switch_instant_switches_at_once(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """With the option a mode switch is instant and the sensors stay live."""
    storage, entry = _setup(hass, "switch_instant", instant=True)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _armed_away(hass)

        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "armed_home")

        # no unwatched window after the switch: the door trips at once
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "pending")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_mode_switch_instant_keeps_exit_delay_from_disarmed(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """The option only affects armed-to-armed: arming from disarmed still waits."""
    storage, entry = _setup(hass, "switch_from_disarmed", instant=True)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        hass.states.async_set(WINDOW, "off")
        await _settle(hass)

        await _arm(hass, "home")
        assert_alarm_state(hass, ALARM_ENTITY, "arming")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_mode_switch_instant_with_open_window_reverts(
    hass: Any, enable_custom_integrations: Any
) -> None:
    """An open blocking sensor fails the instant switch; the old mode stays."""
    storage, entry = _setup(hass, "switch_blocked", instant=True)
    events: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", events.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _armed_away(hass)

        # the window is not watched in away mode, so opening it changes nothing
        hass.states.async_set(WINDOW, "on")
        await _settle(hass)
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")

        await _arm(hass, "home")
        await hass.async_block_till_done()

        # the window is watched in home mode and is open: the switch fails
        assert_alarm_state(hass, ALARM_ENTITY, "armed_away")
        assert [e.data["reason"] for e in events] == ["open_sensors"]
        assert events[0].data["sensors"] == [WINDOW]
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_store_loads_mode_switch_instant(hass: Any) -> None:
    """The option loads from storage and defaults to off when missing."""
    base_config = {
        "code_arm_required": False,
        "code_mode_change_required": False,
        "code_disarm_required": False,
        "code_format": "number",
        "disarm_after_trigger": False,
    }
    for stored, expected in (
        ({}, False),
        ({"mode_switch_instant": True}, True),
        ({"mode_switch_instant": False}, False),
    ):
        storage = AlarmoStorage(hass)
        data = {"config": {**base_config, **stored}}
        with patch.object(storage._store, "async_load", AsyncMock(return_value=data)):
            await storage.async_load()
        assert storage.async_get_config()["mode_switch_instant"] is expected
