"""The Cosori Airfryer integration (VeSync cloud via pyvesync)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError, VeSyncLoginError

from .const import CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE, DOMAIN
from .coordinator import CosoriConfigEntry, CosoriCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


FRONTEND_URL = f"/{DOMAIN}"
FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and the dashboard card."""
    async_setup_services(hass)
    version = await hass.async_add_executor_job(_manifest_version)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), True)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL}/cosori-airfryer-card.js?v={version}")
    return True


def _manifest_version() -> str:
    manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
    return manifest.get("version", "0")


async def async_setup_entry(hass: HomeAssistant, entry: CosoriConfigEntry) -> bool:
    """Set up Cosori Airfryer from a config entry."""
    manager = VeSync(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        country_code=entry.data.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE),
        session=async_get_clientsession(hass),
        time_zone=str(hass.config.time_zone),
    )
    try:
        await manager.login()
        await manager.get_devices()
    except VeSyncLoginError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (VeSyncError, TimeoutError) as err:
        raise ConfigEntryNotReady(f"VeSync not reachable: {err}") from err

    if not manager.devices.air_fryers:
        _LOGGER.warning(
            "No air fryer found in VeSync account. Device types: %s",
            [dev.device_type for dev in manager.devices],
        )

    coordinator = CosoriCoordinator(hass, entry, manager)
    await coordinator.async_load_settings()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CosoriConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_delayed_refresh(coordinator: CosoriCoordinator, delay: float) -> None:
    """Refresh the coordinator a moment after a command."""
    await asyncio.sleep(delay)
    await coordinator.async_request_refresh()
