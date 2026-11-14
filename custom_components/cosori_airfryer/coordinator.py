"""Data update coordinator for the Cosori Airfryer integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyvesync import VeSync
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerChamber, AirFryerCookStatus
from pyvesync.utils.errors import (
    VeSyncError,
    VeSyncLoginError,
    VeSyncTokenError,
)

from .const import DOMAIN, SCAN_INTERVAL_ACTIVE, SCAN_INTERVAL_IDLE

_LOGGER = logging.getLogger(__name__)

type CosoriConfigEntry = ConfigEntry[CosoriCoordinator]

ACTIVE_STATUSES = {
    AirFryerCookStatus.COOKING,
    AirFryerCookStatus.HEATING,
    AirFryerCookStatus.HOLD,
    AirFryerCookStatus.COOK_STOP,
    AirFryerCookStatus.PULL_OUT,
    AirFryerCookStatus.READY,
    AirFryerCookStatus.PREHEAT_END,
    AirFryerCookStatus.PREHEAT_STOP,
    AirFryerCookStatus.APPOINTING,
}


@dataclass
class StartSettings:
    """Cook settings used by the start button (one per fryer)."""

    chamber: str = "chamber_1"
    mode: str | None = None
    temperature: int | None = None
    duration_min: int | None = None
    listeners: list = field(default_factory=list)

    def notify(self) -> None:
        """Tell the setting entities to write their state."""
        for listener in self.listeners:
            listener()


def chamber_states(fryer: VeSyncFryer) -> list[tuple[AirFryerChamber, FryerState]]:
    """Return the single-chamber states of a fryer."""
    states = [(AirFryerChamber.CHAMBER_1, fryer.state_chamber_1)]
    if fryer.is_dual_chamber:
        states.append((AirFryerChamber.CHAMBER_2, fryer.state_chamber_2))
    return states


def is_active(fryer: VeSyncFryer) -> bool:
    """Return True if any chamber of the fryer is busy."""
    return any(
        state.cook_status in ACTIVE_STATUSES for _, state in chamber_states(fryer)
    )


class CosoriCoordinator(DataUpdateCoordinator[None]):
    """Poll all Cosori air fryers of a VeSync account."""

    config_entry: CosoriConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: CosoriConfigEntry, manager: VeSync
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_IDLE,
        )
        self.manager = manager
        self.fryers: dict[str, VeSyncFryer] = {
            fryer.cid: fryer for fryer in manager.devices.air_fryers
        }
        self.settings: dict[str, StartSettings] = {
            cid: StartSettings() for cid in self.fryers
        }

    async def _async_update_data(self) -> None:
        """Fetch the latest status of every fryer."""
        try:
            for fryer in self.fryers.values():
                await fryer.update()
        except (VeSyncLoginError, VeSyncTokenError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VeSyncError as err:
            raise UpdateFailed(f"VeSync error: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed("Timeout talking to VeSync") from err

        busy = any(is_active(fryer) for fryer in self.fryers.values())
        self.update_interval = SCAN_INTERVAL_ACTIVE if busy else SCAN_INTERVAL_IDLE
