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
