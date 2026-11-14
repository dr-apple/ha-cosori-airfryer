"""Services for the Cosori Airfryer integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .actions import async_end_cooking, async_start_cooking
from .const import (
    ATTR_CHAMBER,
    ATTR_DURATION,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    CHAMBER_OPTIONS,
    DOMAIN,
    SERVICE_END_COOKING,
    SERVICE_START_COOKING,
)
from .coordinator import CosoriCoordinator

START_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_CHAMBER, default="chamber_1"): vol.In(list(CHAMBER_OPTIONS)),
        vol.Optional(ATTR_MODE): cv.string,
        vol.Optional(ATTR_TEMPERATURE): vol.Coerce(int),
        vol.Optional(ATTR_DURATION): vol.Coerce(int),
    }
)

END_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_CHAMBER, default="both"): vol.In(list(CHAMBER_OPTIONS)),
    }
)


def _resolve(hass: HomeAssistant, device_id: str):
    """Return (coordinator, fryer) for a device id."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_device"
        )
    cid = next((ident for dom, ident in device.identifiers if dom == DOMAIN), None)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        coordinator: CosoriCoordinator = entry.runtime_data
        if cid in coordinator.fryers:
            return coordinator, coordinator.fryers[cid]
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="unknown_device"
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services."""

    async def _start(call: ServiceCall) -> None:
        coordinator, fryer = _resolve(hass, call.data[ATTR_DEVICE_ID])
        await async_start_cooking(
            coordinator,
            fryer,
            call.data[ATTR_CHAMBER],
            call.data.get(ATTR_MODE),
            call.data.get(ATTR_TEMPERATURE),
            call.data.get(ATTR_DURATION),
        )

    async def _end(call: ServiceCall) -> None:
        coordinator, fryer = _resolve(hass, call.data[ATTR_DEVICE_ID])
        chamber = call.data[ATTR_CHAMBER]
        if chamber == "both" and not fryer.is_dual_chamber:
            chamber = "chamber_1"
        await async_end_cooking(coordinator, fryer, chamber)

    hass.services.async_register(DOMAIN, SERVICE_START_COOKING, _start, START_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_END_COOKING, _end, END_SCHEMA)
