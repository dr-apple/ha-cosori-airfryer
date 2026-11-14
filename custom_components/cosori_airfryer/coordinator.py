"""Data update coordinator for the Cosori Airfryer integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyvesync import VeSync
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerChamber, AirFryerCookStatus, AirFryerFeatures
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
class ChamberSettings:
    """Cook settings of one basket."""

    mode: str | None = None
    temperature: int | None = None
    duration_min: int | None = None


@dataclass
class StartSettings:
    """What the start button does (one per fryer, stored across restarts).

    ``chamber`` is the basket being edited/started (chamber_1, chamber_2,
    whole). ``link`` couples both baskets like the fryer's buttons:
    ``sync`` = own settings per basket, both finish together;
    ``match`` = basket 2 copies basket 1.
    """

    chamber: str = "chamber_1"
    link: str = "off"
    per: dict[int, ChamberSettings] = field(
        default_factory=lambda: {1: ChamberSettings(), 2: ChamberSettings()}
    )
    listeners: list = field(default_factory=list)
    on_change: Callable[[], None] | None = None

    @property
    def key(self) -> int:
        """Basket whose settings the controls show."""
        if self.link == "match" or self.chamber != "chamber_2":
            return 1
        return 2

    @property
    def current(self) -> ChamberSettings:
        """Settings of the basket being edited."""
        return self.per[self.key]

    def notify(self) -> None:
        """Write the setting entities' state and persist."""
        for listener in self.listeners:
            listener()
        if self.on_change:
            self.on_change()

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "chamber": self.chamber,
            "link": self.link,
            "per": {str(k): asdict(v) for k, v in self.per.items()},
        }

    def load(self, data: dict[str, Any]) -> None:
        """Restore from storage."""
        if data.get("chamber") in ("chamber_1", "chamber_2", "whole"):
            self.chamber = data["chamber"]
        if data.get("link") in ("off", "sync", "match"):
            self.link = data["link"]
        for k, v in (data.get("per") or {}).items():
            if int(k) in self.per and isinstance(v, dict):
                self.per[int(k)] = ChamberSettings(
                    v.get("mode"), v.get("temperature"), v.get("duration_min")
                )


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
        # The TwinFry uses the same startMultiCook API as the CAF-DC111S,
        # where pyvesync enables separate settings per basket (Sync/Match).
        for fryer in self.fryers.values():
            if (
                AirFryerFeatures.WHOLE_CHAMBER in fryer.features
                and AirFryerFeatures.CHAMBER_MODES not in fryer.features
            ):
                fryer.features = [*fryer.features, AirFryerFeatures.CHAMBER_MODES]
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.settings"
        )
        self._save_debouncer = Debouncer(
            hass, _LOGGER, cooldown=2, immediate=False, function=self._async_save
        )
        self.settings: dict[str, StartSettings] = {}
        for cid in self.fryers:
            settings = StartSettings()
            settings.on_change = self._save_debouncer.async_schedule_call
            self.settings[cid] = settings

    async def async_load_settings(self) -> None:
        """Load stored start settings."""
        data = await self._store.async_load() or {}
        for cid, settings in self.settings.items():
            if isinstance(data.get(cid), dict):
                settings.load(data[cid])

    async def async_shutdown(self) -> None:
        """Save pending settings and stop the save timer."""
        self._save_debouncer.async_cancel()
        await self._async_save()
        await super().async_shutdown()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {cid: s.as_dict() for cid, s in self.settings.items()}
        )

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
