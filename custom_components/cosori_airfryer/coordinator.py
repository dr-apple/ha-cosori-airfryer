"""Data update coordinator for the Cosori Airfryer integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from pyvesync import VeSync
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerChamber, AirFryerCookStatus, AirFryerFeatures
from pyvesync.utils.errors import (
    VeSyncError,
    VeSyncLoginError,
    VeSyncTokenError,
)

from .const import DOMAIN, SCAN_INTERVAL_ACTIVE, SCAN_INTERVAL_IDLE
from .live_activity import LiveActivityManager
from .notifications import FinishNotifier

_LOGGER = logging.getLogger(__name__)

# A planned start that HA missed (e.g. it was restarting) still runs if it is
# at most this late; otherwise it is dropped with a notification.
PLAN_GRACE = timedelta(minutes=10)

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
    # Planned start: time, whether it is "start at" or "finish at", armed,
    # and the settings frozen when it was armed.
    plan_at: datetime | None = None
    plan_type: str = "start"
    plan_armed: bool = False
    plan_snapshot: dict[str, Any] | None = None
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

    def cook_dict(self) -> dict[str, Any]:
        """The cook settings only (what a planned start freezes)."""
        return {
            "chamber": self.chamber,
            "link": self.link,
            "per": {str(k): asdict(v) for k, v in self.per.items()},
        }

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            **self.cook_dict(),
            "plan": {
                "at": self.plan_at.isoformat() if self.plan_at else None,
                "type": self.plan_type,
                "armed": self.plan_armed,
                "snapshot": self.plan_snapshot,
            },
        }

    @classmethod
    def from_cook_dict(cls, data: dict[str, Any]) -> StartSettings:
        """Build settings from a frozen cook dict."""
        settings = cls()
        settings.load(data)
        return settings

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
        plan = data.get("plan") or {}
        if plan.get("at"):
            self.plan_at = dt_util.parse_datetime(plan["at"])
        if plan.get("type") in ("start", "finish"):
            self.plan_type = plan["type"]
        self.plan_armed = bool(plan.get("armed")) and self.plan_at is not None
        self.plan_snapshot = plan.get("snapshot") if self.plan_armed else None


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
        self.notifier = FinishNotifier(hass, entry)
        self.live = LiveActivityManager(hass, entry)
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
        self._plan_unsub: dict[str, CALLBACK_TYPE] = {}
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
            if settings.plan_armed:
                self._restore_plan(cid)

    # ---------------------------------------------------------------- plans

    def plan_start_time(self, cid: str) -> datetime | None:
        """When the fryer will actually be started."""
        s = self.settings[cid]
        if s.plan_at is None:
            return None
        if s.plan_type == "start":
            return s.plan_at
        snap = StartSettings.from_cook_dict(s.plan_snapshot or s.cook_dict())
        return s.plan_at - timedelta(minutes=self._longest_minutes(cid, snap))

    def _longest_minutes(self, cid: str, snap: StartSettings) -> int:
        from .actions import default_duration_min  # noqa: PLC0415

        fryer = self.fryers[cid]
        baskets = [1, 2] if snap.link in ("sync", "match") else [snap.key]
        if snap.link == "match":
            baskets = [1]
        if snap.chamber == "whole":
            baskets = [1]
        return max(
            (
                snap.per[n].duration_min
                if snap.per[n].duration_min is not None
                else default_duration_min(fryer, snap.per[n].mode)
            )
            for n in baskets
        )

    @callback
    def async_arm_plan(self, cid: str) -> None:
        """Freeze the current settings and schedule the start."""
        s = self.settings[cid]
        if s.plan_at is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="plan_no_time"
            )
        s.plan_snapshot = s.cook_dict()
        start = self.plan_start_time(cid)
        if start is None or start <= dt_util.utcnow() + timedelta(seconds=30):
            s.plan_snapshot = None
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="plan_in_past"
            )
        s.plan_armed = True
        self._schedule(cid)
        s.notify()

    @callback
    def async_disarm_plan(self, cid: str) -> None:
        """Cancel a planned start."""
        s = self.settings[cid]
        if unsub := self._plan_unsub.pop(cid, None):
            unsub()
        s.plan_armed = False
        s.plan_snapshot = None
        s.notify()

    @callback
    def _schedule(self, cid: str) -> None:
        if unsub := self._plan_unsub.pop(cid, None):
            unsub()
        start = self.plan_start_time(cid)
        if start is None:
            return

        async def _fire(_now: datetime) -> None:
            self._plan_unsub.pop(cid, None)
            await self._async_run_plan(cid)

        self._plan_unsub[cid] = async_track_point_in_time(self.hass, _fire, start)

    @callback
    def _restore_plan(self, cid: str) -> None:
        start = self.plan_start_time(cid)
        now = dt_util.utcnow()
        if start is None:
            self.settings[cid].plan_armed = False
            return
        if start < now - PLAN_GRACE:
            name = self.fryers[cid].device_name.strip()
            persistent_notification.async_create(
                self.hass,
                f"Der geplante Start ({dt_util.as_local(start):%d.%m. %H:%M}) wurde "
                "verpasst, weil Home Assistant nicht lief. Der Plan wurde verworfen.",
                title=f"{name}: geplanter Start verpasst",
                notification_id=f"{DOMAIN}_{cid}_plan",
            )
            self.settings[cid].plan_armed = False
            self.settings[cid].plan_snapshot = None
            return
        self._schedule(cid)

    async def _async_run_plan(self, cid: str) -> None:
        from .actions import async_start_from_settings  # noqa: PLC0415

        s = self.settings[cid]
        snap = StartSettings.from_cook_dict(s.plan_snapshot or s.cook_dict())
        name = self.fryers[cid].device_name.strip()
        try:
            await async_start_from_settings(self, self.fryers[cid], snap)
        except HomeAssistantError as err:
            _LOGGER.error("Planned start of %s failed: %s", name, err)
            persistent_notification.async_create(
                self.hass,
                f"Der geplante Start ist fehlgeschlagen: {err}",
                title=f"{name}: geplanter Start fehlgeschlagen",
                notification_id=f"{DOMAIN}_{cid}_plan",
            )
        finally:
            s.plan_armed = False
            s.plan_snapshot = None
            s.notify()

    async def async_shutdown(self) -> None:
        """Save pending settings and stop the timers."""
        for unsub in self._plan_unsub.values():
            unsub()
        self._plan_unsub.clear()
        self.live.async_shutdown()
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
        await self.notifier.async_process(self.fryers)
        await self.live.async_process(self.fryers)
