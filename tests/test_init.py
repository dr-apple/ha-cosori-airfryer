"""Smoke tests with a simulated CAF-TF101S (no network)."""

from unittest.mock import AsyncMock, PropertyMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pyvesync import VeSync
from pyvesync.models.vesync_models import ResponseDeviceDetailsModel

from custom_components.cosori_airfryer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

CID = "vssc5a1b2c3d4e5f6"

DEVICE = {
    "deviceRegion": "EU",
    "deviceType": "CAF-TF101S-AEUR",
    "isOwner": True,
    "deviceName": "Airfryer",
    "deviceImg": "",
    "cid": CID,
    "uuid": "uuid-1",
    "macID": "b0:a7:32:5c:51:a4",
    "connectionType": "wifi",
    "type": "SKA",
    "configModule": "WiFi_AirFryer_CAF-TF101S_EU",
    "mode": None,
    "speed": None,
    "currentFirmVersion": "1.0.07",
    "subDeviceNo": None,
    "extension": None,
    "deviceProps": None,
    "deviceStatus": "on",
    "connectionStatus": "online",
}


def chamber(n: int, status: str, remaining: int = 1140) -> dict:
    active = status != "standby"
    return {
        "cookStatus": status,
        "startTime": 1768667721 if active else 0,
        "recipeType": 3,
        "recipeId": 14,
        "recipeName": "Heißluft" if active else "",
        "upc": "",
        "holdTime": 0,
        "cookSetTime": 1200 if active else 0,
        "cookTemp": 200 if active else 0,
        "mode": "AirFry",
        "currentRemainingTime": remaining if active else 0,
        "totalTimeRemaining": remaining if active else 0,
        "chamber": n,
    }


def response(inner: dict) -> tuple[dict, int]:
    return (
        {
            "traceId": "1",
            "code": 0,
            "msg": "request success",
            "result": {"traceId": "1", "code": 0, "result": inner},
        },
        200,
    )


STATUS = {
    "statusList": [chamber(1, "cooking"), chamber(2, "standby")],
    "tempUnit": "c",
    "syncType": 0,
    "workChamber": 1,
}


def _body(api) -> dict:
    body = api.call_args.kwargs.get("json_object")
    if body is None:
        body = api.call_args.args[2]
    return body if isinstance(body, dict) else body.to_dict()


async def _get_devices(self) -> bool:
    self.devices.add_device_from_model(
        ResponseDeviceDetailsModel.from_dict(DEVICE), self
    )
    return True


async def test_setup_and_start(hass: HomeAssistant) -> None:
    """Set up, read states, start and end a cook."""
    hass.config.language = "de"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "a@b.c", "password": "x", "country_code": "DE"},
        unique_id="a@b.c",
    )
    entry.add_to_hass(hass)
    api = AsyncMock(return_value=response(STATUS))
    with (
        patch.object(VeSync, "login", AsyncMock(return_value=True)),
        patch.object(VeSync, "get_devices", _get_devices),
        patch.object(VeSync, "async_call_api", api),
        patch.object(VeSync, "account_id", new_callable=PropertyMock, return_value="42"),
        patch.object(VeSync, "token", new_callable=PropertyMock, return_value="tok"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        states = {s.entity_id: s.state for s in hass.states.async_all()}
        for eid, st in sorted(states.items()):
            print(eid, st)
        assert states["sensor.airfryer_korb_1_status"] == "cooking"
        assert states["sensor.airfryer_korb_2_status"] == "standby"
        assert states["binary_sensor.airfryer_korb_1_gart"] == "on"
        assert float(states["sensor.airfryer_korb_1_restzeit"]) > 18
        assert states["sensor.airfryer_aktiver_korb"] == "chamber_1"

        # Configure and start: whole basket, Grill, out-of-range temp is clamped.
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_korb", "option": "whole"}, blocking=True,
        )
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_programm", "option": "grill"}, blocking=True,
        )
        assert hass.states.get("number.airfryer_temperatur").state == "240"
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.airfryer_garzeit", "value": 12}, blocking=True,
        )
        api.reset_mock()
        api.return_value = response({})
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.airfryer_garen_starten"}, blocking=True,
        )
        body = _body(api)
        payload = body["payload"]
        print("START", payload)
        data = payload["data"]
        assert payload["method"] == "startMultiCook"
        assert data["workChamber"] == 3
        assert data["cookConfigs"][0]["mode"] == "Grill"
        assert data["cookConfigs"][0]["cookTemp"] == 240
        assert data["cookConfigs"][0]["cookSetTime"] == 720

        # Service: both baskets, airfry 180 °C 10 min.
        api.reset_mock()
        dev_id = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
        await hass.services.async_call(
            DOMAIN, "start_cooking",
            {"device_id": dev_id, "chamber": "both", "mode": "airfry",
             "temperature": 180, "duration": 10},
            blocking=True,
        )
        body = _body(api)
        data = body["payload"]["data"]
        print("SERVICE", data)
        assert data["workChamber"] == 4 and data["syncType"] == 2
        assert len(data["cookConfigs"]) == 2

        # Per-basket settings + SYNC: basket 1 grill 12 min, basket 2 bake 160 °C 30 min.
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_korb", "option": "chamber_2"}, blocking=True,
        )
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_programm", "option": "bake"}, blocking=True,
        )
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.airfryer_temperatur", "value": 160}, blocking=True,
        )
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.airfryer_garzeit", "value": 30}, blocking=True,
        )
        await hass.services.async_call(
            "switch", "turn_on",
            {"entity_id": "switch.airfryer_sync_gleichzeitig_fertig"}, blocking=True,
        )
        attrs = hass.states.get("button.airfryer_garen_starten").attributes
        print("ATTRS", dict(attrs))
        assert attrs["link"] == "sync"
        assert attrs["chamber_2"] == {"mode": "bake", "temperature": 160, "duration": 30}
        api.reset_mock()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.airfryer_garen_starten"}, blocking=True,
        )
        data = _body(api)["payload"]["data"]
        print("SYNC", data)
        assert data["workChamber"] == 4 and data["syncType"] == 2
        c1, c2 = data["cookConfigs"]
        assert (c1["chamber"], c1["mode"], c1["cookTemp"], c1["cookSetTime"]) == (1, "Grill", 240, 720)
        assert (c2["chamber"], c2["mode"], c2["cookTemp"], c2["cookSetTime"]) == (2, "Bake", 160, 1800)

        # MATCH: both baskets get basket 1's settings, SYNC goes off.
        await hass.services.async_call(
            "switch", "turn_on",
            {"entity_id": "switch.airfryer_match_gleiche_einstellungen"}, blocking=True,
        )
        assert hass.states.get("switch.airfryer_sync_gleichzeitig_fertig").state == "off"
        assert hass.states.get("select.airfryer_programm").state == "grill"
        api.reset_mock()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.airfryer_garen_starten"}, blocking=True,
        )
        data = _body(api)["payload"]["data"]
        print("MATCH", data)
        assert data["workChamber"] == 4 and data["syncType"] == 1
        assert [c["mode"] for c in data["cookConfigs"]] == ["Grill", "Grill"]

        # MATCH off again -> only the selected basket (2) starts.
        await hass.services.async_call(
            "switch", "turn_off",
            {"entity_id": "switch.airfryer_match_gleiche_einstellungen"}, blocking=True,
        )
        api.reset_mock()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.airfryer_garen_starten"}, blocking=True,
        )
        data = _body(api)["payload"]["data"]
        assert data["workChamber"] == 2 and data["cookConfigs"][0]["mode"] == "Bake"

        api.reset_mock()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.airfryer_alles_beenden"}, blocking=True,
        )
        body = _body(api)
        assert body["payload"]["method"] == "endCook"
        assert body["payload"]["data"] == {"chamber": 4}

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_planned_start(hass: HomeAssistant) -> None:
    """Plan 'finish at' with frozen settings; it fires once at the right time."""
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from homeassistant.util import dt as dt_util

    hass.config.language = "de"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "a@b.c", "password": "x", "country_code": "DE"},
        unique_id="a@b.c",
    )
    entry.add_to_hass(hass)
    idle = {**STATUS, "statusList": [chamber(1, "standby"), chamber(2, "standby")], "workChamber": 0}
    api = AsyncMock(return_value=response(idle))
    with (
        patch.object(VeSync, "login", AsyncMock(return_value=True)),
        patch.object(VeSync, "get_devices", _get_devices),
        patch.object(VeSync, "async_call_api", api),
        patch.object(VeSync, "account_id", new_callable=PropertyMock, return_value="42"),
        patch.object(VeSync, "token", new_callable=PropertyMock, return_value="tok"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = sorted(s.entity_id for s in hass.states.async_all() if "plan" in s.entity_id or "geplant" in s.entity_id or "zeit" in s.entity_id)
        print("PLAN IDS", ids)

        # Korb 2, Backen 160 °C 30 min, finish in 2 h.
        for svc, dom, data in (
            ("select_option", "select", {"entity_id": "select.airfryer_korb", "option": "chamber_2"}),
            ("select_option", "select", {"entity_id": "select.airfryer_programm", "option": "bake"}),
            ("set_value", "number", {"entity_id": "number.airfryer_temperatur", "value": 160}),
            ("set_value", "number", {"entity_id": "number.airfryer_garzeit", "value": 30}),
        ):
            await hass.services.async_call(dom, svc, data, blocking=True)
        finish = (dt_util.now() + timedelta(hours=2)).replace(second=0, microsecond=0)
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_geplante_zeit_ist", "option": "finish"}, blocking=True,
        )
        await hass.services.async_call(
            "datetime", "set_value",
            {"entity_id": "datetime.airfryer_geplante_zeit", "datetime": finish}, blocking=True,
        )
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.airfryer_zeitplan_aktiv"}, blocking=True,
        )
        start = dt_util.parse_datetime(hass.states.get("sensor.airfryer_geplanter_start").state)
        assert start == finish - timedelta(minutes=30)
        attrs = hass.states.get("switch.airfryer_zeitplan_aktiv").attributes
        assert attrs["chamber"] == "chamber_2" and attrs["chamber_2"]["mode"] == "bake"

        # Later edits do not change the frozen plan.
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_programm", "option": "grill"}, blocking=True,
        )
        api.reset_mock()
        async_fire_time_changed(hass, start - timedelta(minutes=1))
        await hass.async_block_till_done()
        assert not any(_body_any(c).get("payload", {}).get("method") == "startMultiCook" for c in api.call_args_list)

        async_fire_time_changed(hass, start + timedelta(seconds=1))
        await hass.async_block_till_done()
        starts = [_body_any(c) for c in api.call_args_list if _body_any(c).get("payload", {}).get("method") == "startMultiCook"]
        assert len(starts) == 1
        data = starts[0]["payload"]["data"]
        print("PLANNED START", data)
        assert data["workChamber"] == 2 and data["cookConfigs"][0]["mode"] == "Bake"
        assert data["cookConfigs"][0]["cookTemp"] == 160 and data["cookConfigs"][0]["cookSetTime"] == 1800
        assert hass.states.get("switch.airfryer_zeitplan_aktiv").state == "off"
        assert hass.states.get("sensor.airfryer_geplanter_start").state == "unknown"

        # A plan in the past is refused.
        import pytest

        from homeassistant.exceptions import ServiceValidationError

        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.airfryer_geplante_zeit_ist", "option": "start"}, blocking=True,
        )
        await hass.services.async_call(
            "datetime", "set_value",
            {"entity_id": "datetime.airfryer_geplante_zeit", "datetime": dt_util.now() - timedelta(hours=1)},
            blocking=True,
        )
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.airfryer_zeitplan_aktiv"}, blocking=True,
            )
        assert await hass.config_entries.async_unload(entry.entry_id)


def _body_any(call) -> dict:
    body = call.kwargs.get("json_object")
    if body is None and len(call.args) > 2:
        body = call.args[2]
    if body is None:
        return {}
    return body if isinstance(body, dict) else body.to_dict()
