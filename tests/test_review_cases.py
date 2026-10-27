# ha_alarmo fork (Apache-2.0 section 4b), combined branch "patches": new test file.
"""Review cases for the five patches.

Master entity, unavailable sensor, option off, redundant disarm (AF1ar review).
"""

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

AREA = "alarm_control_panel.test_area_1"
MASTER = "alarm_control_panel.master"
DOOR = "binary_sensor.back_door"
CODE = "1234"


def _setup(hass, entry_id, master=False, exit_time=10, instant=None):
    areas = [
        AreaFactory.create_area(
            area_id="area_1",
            modes=["armed_away", "armed_home"],
            armed_away_exit_time=exit_time,
            armed_away_entry_time=30,
            armed_home_exit_time=exit_time,
            armed_home_entry_time=30,
        )
    ]
    if master:
        areas.append(
            AreaFactory.create_area(
                area_id="area_2",
                name="Test Area 2",
                modes=["armed_away", "armed_home"],
                armed_away_exit_time=exit_time,
                armed_home_exit_time=exit_time,
            )
        )
    door = SensorFactory.create_door_sensor(
        entity_id=DOOR,
        name="Back Door",
        area="area_1",
        modes=["armed_away", "armed_home"],
        auto_bypass=True,
        auto_bypass_modes=["armed_away", "armed_home"],
    )
    storage, entry = setup_alarmo_entry(
        hass, areas=areas, sensors=[door], entry_id=entry_id, master_enabled=master
    )
    if instant is not None:
        storage.config["mode_switch_instant"] = instant
    return storage, entry


async def _settle(hass):
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _call(hass, service, entity=AREA, **data):
    await hass.services.async_call(
        "alarmo", service, {"entity_id": entity, **data}, blocking=True
    )
    await _settle(hass)


@pytest.mark.asyncio
async def test_master_refusals_raise_and_report(
    hass: Any, enable_custom_integrations: Any
):
    """Master entity: refusals raise and fire alarmo_failed_to_arm with the reason."""
    storage, entry = _setup(hass, "rv_master", master=True)
    failed: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", failed.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await _settle(hass)
        await _call(hass, "arm", entity=MASTER, code=CODE, mode="away")
        assert_alarm_state(hass, MASTER, "arming")
        with pytest.raises(ServiceValidationError):
            await _call(hass, "arm", entity=MASTER, code=CODE, mode="home")
        await _settle(hass)
        assert [e.data["reason"] for e in failed] == ["not_allowed"]
        failed.clear()
        await advance_time(hass, 11)
        assert_alarm_state(hass, MASTER, "armed_away")
        await _call(hass, "arm", entity=MASTER, code=CODE, mode="away")
        assert [e.data["reason"] for e in failed] == ["already_armed"]
        failed.clear()
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        assert_alarm_state(hass, AREA, "pending")
        assert_alarm_state(hass, MASTER, "pending")
        with pytest.raises(ServiceValidationError):
            await _call(hass, "skip_delay", entity=MASTER)
        await _settle(hass)
        assert_alarm_state(hass, AREA, "pending")
        assert [(e.data["reason"], e.data["command"]) for e in failed] == [
            ("not_allowed", "skip_delay")
        ]
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_unavailable_bypassed_sensor_stays_bypassed(
    hass: Any, enable_custom_integrations: Any
):
    """An unavailable bypassed sensor is not rejoined by a same-mode arm or unbypass."""
    storage, entry = _setup(hass, "rv_unavail", exit_time=0)
    failed: list[Event] = []
    hass.bus.async_listen("alarmo_failed_to_arm", failed.append)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "on")
        await _settle(hass)
        await _call(hass, "arm", code=CODE, mode="away")
        assert_alarm_state(hass, AREA, "armed_away")
        assert hass.states.get(AREA).attributes["bypassed_sensors"] == [DOOR]
        hass.states.async_set(DOOR, "unavailable")
        await _settle(hass)
        await _call(hass, "arm", code=CODE, mode="away")
        assert_alarm_state(hass, AREA, "armed_away")
        assert hass.states.get(AREA).attributes["bypassed_sensors"] == [DOOR]
        assert [e.data["reason"] for e in failed] == ["already_armed"]
        resp = await hass.services.async_call(
            "alarmo",
            "unbypass",
            {"entity_id": AREA, "sensors": ["binary_sensor.nope"]},
            blocking=True,
            return_response=True,
        )
        assert resp[AREA] == {"rejoined": [], "still_bypassed": [DOOR]}
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_mode_switch_option_explicit_off_keeps_delay(
    hass: Any, enable_custom_integrations: Any
):
    """mode_switch_instant set to False keeps the exit delay on a mode switch."""
    storage, entry = _setup(hass, "rv_off", instant=False)
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(DOOR, "off")
        await _settle(hass)
        await _call(hass, "arm", code=CODE, mode="away")
        await advance_time(hass, 11)
        assert_alarm_state(hass, AREA, "armed_away")
        await _call(hass, "arm", code=CODE, mode="home")
        assert_alarm_state(hass, AREA, "arming")
        await _call(hass, "skip_delay")
        assert_alarm_state(hass, AREA, "armed_home")
        await cleanup_timers(hass)


@pytest.mark.asyncio
async def test_disarm_from_disarmed_unchanged(
    hass: Any, enable_custom_integrations: Any
):
    """Patch 1 is about arm commands only: a redundant disarm still does not raise."""
    storage, entry = _setup(hass, "rv_disarm")
    with patch_alarmo_integration_dependencies(storage):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _call(hass, "disarm", code=CODE)
        assert_alarm_state(hass, AREA, "disarmed")
        await cleanup_timers(hass)
