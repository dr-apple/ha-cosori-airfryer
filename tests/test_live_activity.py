"""Live Activities while cooking: per basket, shared for Sync, done and cleared."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.cosori_airfryer.const import CONF_LIVE_ACTIVITY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_init import STATUS, chamber, response
from .test_notifications import _entry, _setup


def _st(c1: tuple[str, int], c2: tuple[str, int], work: int = 1) -> dict:
    return {
        **STATUS,
        "workChamber": work,
        "statusList": [chamber(1, c1[0], c1[1]), chamber(2, c2[0], c2[1])],
    }


async def _poll(fryer, c1, c2, work: int = 1) -> list[dict]:
    fryer.api.return_value = response(_st(c1, c2, work))
    fryer.calls.clear()
    await fryer.entry.runtime_data.async_refresh()
    await fryer.hass.async_block_till_done()
    return [c.data for c in fryer.calls]


def _tags(calls: list[dict]) -> list[str]:
    return [c["data"]["tag"].rsplit("_", 1)[-1] if "basket" not in c["data"]["tag"]
            else "basket_" + c["data"]["tag"].rsplit("_", 1)[-1] for c in calls]


async def test_per_basket_then_done_and_cleared(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_LIVE_ACTIVITY: True})
    fryer, patches = await _setup(hass, entry, _st(("standby", 0), ("standby", 0)))
    try:
        calls = await _poll(fryer, ("cooking", 600), ("cooking", 1500))
        assert sorted(_tags(calls)) == ["basket_1", "basket_2"]
        c1 = next(c for c in calls if c["data"]["tag"].endswith("basket_1"))
        assert c1["title"] == "Airfryer · Korb 1"
        assert c1["message"] == "Heißluft · 200 °C · gart"
        d = c1["data"]
        assert d["live_update"] is True and d["chronometer"] is True
        assert d["progress"] == 600 and d["progress_max"] == 1200
        assert d["when_relative"] is False and d["when"] > dt_util.utcnow().timestamp()

        # Same state again: no push (iOS throttles updates).
        assert await _poll(fryer, ("cooking", 600), ("cooking", 1500)) == []

        # Basket 1 done while basket 2 runs on: green, with sound, no extra push.
        calls = await _poll(fryer, ("cookEnd", 0), ("cooking", 1170))
        done = [c for c in calls if c["data"]["tag"].endswith("basket_1")]
        assert len(done) == 1
        assert done[0]["message"] == "Korb 1 ist fertig. Korb 2 läuft noch 20 min."
        assert done[0]["data"]["silent"] is False
        assert done[0]["data"]["progress"] == done[0]["data"]["progress_max"] == 1200
        assert all(c["data"].get("live_update") for c in calls)

        # Ten minutes later the done activity is removed.
        fryer.calls.clear()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
        await hass.async_block_till_done()
        cleared = [c.data for c in fryer.calls if c.data["message"] == "clear_notification"]
        assert [c["data"]["tag"][-8:] for c in cleared] == ["basket_1"]
    finally:
        for p in patches:
            p.stop()


async def test_sync_shares_one_activity(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_LIVE_ACTIVITY: True})
    fryer, patches = await _setup(hass, entry, _st(("standby", 0), ("standby", 0)))
    try:
        calls = await _poll(fryer, ("cooking", 900), ("hold", 900), work=4)
        assert len(calls) == 1
        assert calls[0]["data"]["tag"].endswith("_both")
        assert calls[0]["title"] == "Airfryer · Korb 1 + 2"
        assert calls[0]["message"] == "1: Heißluft · 200 °C\n2: Heißluft · 200 °C (wartet)"
        calls = await _poll(fryer, ("cookEnd", 0), ("cookEnd", 0), work=4)
        assert [c["message"] for c in calls] == ["Beide Körbe sind fertig."]
    finally:
        for p in patches:
            p.stop()


async def test_ended_by_hand_is_removed_at_once(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_LIVE_ACTIVITY: True})
    fryer, patches = await _setup(hass, entry, _st(("standby", 0), ("standby", 0)))
    try:
        await _poll(fryer, ("cooking", 600), ("standby", 0))
        calls = await _poll(fryer, ("standby", 0), ("standby", 0))
        assert [c["message"] for c in calls] == ["clear_notification"]
    finally:
        for p in patches:
            p.stop()


async def test_off_sends_no_live_updates(hass: HomeAssistant) -> None:
    entry = _entry()
    fryer, patches = await _setup(hass, entry, _st(("standby", 0), ("standby", 0)))
    try:
        assert await _poll(fryer, ("cooking", 600), ("standby", 0)) == []
        calls = await _poll(fryer, ("cookEnd", 0), ("standby", 0))
        assert [c["message"] for c in calls] == ["Korb 1 ist fertig."]
        assert "live_update" not in calls[0]["data"]
    finally:
        for p in patches:
            p.stop()
