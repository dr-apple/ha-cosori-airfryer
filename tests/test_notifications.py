"""Push notifications when baskets finish (per basket when times differ)."""

from datetime import timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)
from pyvesync import VeSync

from custom_components.cosori_airfryer.const import (
    CONF_NOTIFY_APART,
    CONF_NOTIFY_BASKET_2,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_TOGETHER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_init import STATUS, _get_devices, chamber, response


def _status(c1: tuple[str, int], c2: tuple[str, int]) -> dict:
    return {
        **STATUS,
        "statusList": [chamber(1, c1[0], c1[1]), chamber(2, c2[0], c2[1])],
    }


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={"username": "a@b.c", "password": "x", "country_code": "DE"},
        unique_id="a@b.c",
        options={CONF_NOTIFY_ENABLED: True, CONF_NOTIFY_TARGET: "notify.test", **options},
    )


class _Fryer:
    """Drive the simulated cloud one poll at a time."""

    def __init__(self, hass: HomeAssistant, entry: MockConfigEntry, api: AsyncMock):
        self.hass, self.entry, self.api = hass, entry, api
        self.calls = async_mock_service(hass, "notify", "test")

    async def poll(self, c1: tuple[str, int], c2: tuple[str, int]) -> list[str]:
        self.api.return_value = response(_status(c1, c2))
        self.calls.clear()
        await self.entry.runtime_data.async_refresh()
        await self.hass.async_block_till_done()
        return [c.data["message"] for c in self.calls]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, first: dict):
    hass.config.language = "de"
    entry.add_to_hass(hass)
    api = AsyncMock(return_value=response(first))
    patches = (
        patch.object(VeSync, "login", AsyncMock(return_value=True)),
        patch.object(VeSync, "get_devices", _get_devices),
        patch.object(VeSync, "async_call_api", api),
        patch.object(VeSync, "account_id", new_callable=PropertyMock, return_value="42"),
        patch.object(VeSync, "token", new_callable=PropertyMock, return_value="tok"),
    )
    for p in patches:
        p.start()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return _Fryer(hass, entry, api), patches


async def test_baskets_finish_apart_each_announces(hass: HomeAssistant) -> None:
    entry = _entry()
    fryer, patches = await _setup(hass, entry, _status(("cooking", 600), ("cooking", 1500)))
    try:
        # Still running: nothing.
        assert await fryer.poll(("cooking", 300), ("cooking", 1200)) == []
        # Basket 1 done, basket 2 has 20 min left -> own message with the rest.
        msgs = await fryer.poll(("cookEnd", 0), ("cooking", 1170))
        assert msgs == ["Korb 1 ist fertig. Korb 2 läuft noch 20 min."]
        # Basket 2 later -> its own message, too.
        assert await fryer.poll(("standby", 0), ("cooking", 20)) == []
        msgs = await fryer.poll(("standby", 0), ("cookEnd", 0))
        assert msgs == ["Korb 2 ist fertig."]
    finally:
        for p in patches:
            p.stop()


async def test_baskets_finish_together_one_message(hass: HomeAssistant) -> None:
    entry = _entry()
    fryer, patches = await _setup(hass, entry, _status(("cooking", 600), ("cooking", 630)))
    try:
        # Basket 1 is done, basket 2 within the 1 min tolerance -> one message.
        msgs = await fryer.poll(("cookEnd", 0), ("cooking", 40))
        assert msgs == ["Beide Körbe sind fertig."]
        # Basket 2 finishing a moment later must not repeat it.
        assert await fryer.poll(("cookEnd", 0), ("cookEnd", 0)) == []
    finally:
        for p in patches:
            p.stop()


async def test_both_finish_in_same_poll(hass: HomeAssistant) -> None:
    entry = _entry()
    fryer, patches = await _setup(hass, entry, _status(("cooking", 10), ("cooking", 10)))
    try:
        msgs = await fryer.poll(("cookEnd", 0), ("cookEnd", 0))
        assert msgs == ["Beide Körbe sind fertig."]
    finally:
        for p in patches:
            p.stop()


async def test_single_basket_and_options(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_NOTIFY_TOGETHER: False})
    fryer, patches = await _setup(hass, entry, _status(("cooking", 30), ("standby", 0)))
    try:
        # "together" off: a single basket stays silent.
        assert await fryer.poll(("cookEnd", 0), ("standby", 0)) == []
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_NOTIFY_TOGETHER: True}
        )
        assert await fryer.poll(("cooking", 30), ("standby", 0)) == []
        assert await fryer.poll(("cookEnd", 0), ("standby", 0)) == ["Korb 1 ist fertig."]
    finally:
        for p in patches:
            p.stop()


async def test_per_basket_switch_and_disabled(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_NOTIFY_BASKET_2: False})
    fryer, patches = await _setup(hass, entry, _status(("cooking", 1500), ("cooking", 600)))
    try:
        # Basket 2 is switched off: it finishes silently.
        assert await fryer.poll(("cooking", 1300), ("cookEnd", 0)) == []
        # Disabled completely: nothing at all.
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_NOTIFY_ENABLED: False}
        )
        assert await fryer.poll(("cookEnd", 0), ("standby", 0)) == []
    finally:
        for p in patches:
            p.stop()


async def test_manual_stop_is_silent(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_NOTIFY_APART: True})
    fryer, patches = await _setup(hass, entry, _status(("cooking", 900), ("cooking", 900)))
    try:
        # Ended by hand: straight to standby with 15 minutes left.
        assert await fryer.poll(("standby", 0), ("cooking", 880)) == []
        assert await fryer.poll(("standby", 0), ("standby", 0)) == []
    finally:
        for p in patches:
            p.stop()


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = _entry()
    fryer, patches = await _setup(hass, entry, _status(("standby", 0), ("standby", 0)))
    try:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_NOTIFY_ENABLED: True,
                CONF_NOTIFY_TARGET: " notify.iphone ",
                CONF_NOTIFY_APART: False,
                CONF_NOTIFY_TOGETHER: True,
                "notify_tolerance": 5,
                "notify_basket_1": True,
                CONF_NOTIFY_BASKET_2: True,
            },
        )
        assert result["type"] == "create_entry"
        assert entry.options[CONF_NOTIFY_TARGET] == "notify.iphone"
        assert entry.options["notify_tolerance"] == 5
    finally:
        for p in patches:
            p.stop()


async def test_missing_target_falls_back_to_persistent(hass: HomeAssistant) -> None:
    entry = _entry(**{CONF_NOTIFY_TARGET: "notify.does_not_exist"})
    fryer, patches = await _setup(hass, entry, _status(("cooking", 30), ("standby", 0)))
    try:
        # Remove the mocked service so the target is unknown.
        hass.services.async_remove("notify", "test")
        with patch(
            "custom_components.cosori_airfryer.notifications.persistent_notification.async_create"
        ) as create:
            fryer.api.return_value = response(_status(("cookEnd", 0), ("standby", 0)))
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()
        create.assert_called_once()
        assert create.call_args.args[1] == "Korb 1 ist fertig."
    finally:
        for p in patches:
            p.stop()
