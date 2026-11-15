"""Live Activities (iOS) / Live Updates (Android) while the fryer cooks.

Uses the companion app's ``live_update`` notifications: one activity per
basket, or one shared activity when both baskets run together (Sync / Match)
or the whole basket is used. It shows a countdown and a progress bar, and when
the basket is done it turns green with a sound and is removed a few minutes
later. A basket ended by hand removes its activity right away.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerChamber, AirFryerCookStatus

from .const import (
    CONF_LIVE_ACTIVITY,
    CONF_NOTIFY_TARGET,
    DEFAULT_LIVE_ACTIVITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import CosoriConfigEntry

_LOGGER = logging.getLogger(__name__)

RUNNING = {
    AirFryerCookStatus.COOKING,
    AirFryerCookStatus.HEATING,
    AirFryerCookStatus.HOLD,
}
DONE = {AirFryerCookStatus.COOK_END, AirFryerCookStatus.COMPLETED}
# Keep the green "done" activity this long, then remove it.
DONE_LINGER_SECONDS = 10 * 60
# Refresh the progress bar at most this often (iOS throttles updates).
PROGRESS_STEP_SECONDS = 60

ICON = "mdi:toaster-oven"
COLOR_RUN = "#FF9A3C"
COLOR_DONE = "#4CAF50"

TEXTS: dict[str, dict[str, Any]] = {
    "de": {
        "basket": "Korb {n}",
        "both": "Korb 1 + 2",
        "whole": "Ganzer Korb",
        "status": {
            AirFryerCookStatus.COOKING: "gart",
            AirFryerCookStatus.HEATING: "heizt vor",
            AirFryerCookStatus.HOLD: "wartet",
            AirFryerCookStatus.COOK_STOP: "pausiert",
            AirFryerCookStatus.PULL_OUT: "Korb raus",
            AirFryerCookStatus.READY: "wartet auf Start",
            AirFryerCookStatus.PREHEAT_END: "vorgeheizt",
            AirFryerCookStatus.PREHEAT_STOP: "pausiert",
            AirFryerCookStatus.APPOINTING: "geplant",
        },
        "modes": {
            "airfry": "Heißluft", "roast": "Braten", "bake": "Backen",
            "grill": "Grillen", "reheat": "Aufwärmen", "dry": "Trocknen",
        },
        "done_one": "Korb {n} ist fertig.",
        "done_one_rest": "Korb {n} ist fertig. Korb {m} läuft noch {min} min.",
        "done_both": "Beide Körbe sind fertig.",
        "done_whole": "Fertig!",
    },
    "en": {
        "basket": "Basket {n}",
        "both": "Basket 1 + 2",
        "whole": "Whole basket",
        "status": {
            AirFryerCookStatus.COOKING: "cooking",
            AirFryerCookStatus.HEATING: "preheating",
            AirFryerCookStatus.HOLD: "waiting",
            AirFryerCookStatus.COOK_STOP: "paused",
            AirFryerCookStatus.PULL_OUT: "basket out",
            AirFryerCookStatus.READY: "waiting for start",
            AirFryerCookStatus.PREHEAT_END: "preheated",
            AirFryerCookStatus.PREHEAT_STOP: "paused",
            AirFryerCookStatus.APPOINTING: "scheduled",
        },
        "modes": {
            "airfry": "Air fry", "roast": "Roast", "bake": "Bake",
            "grill": "Grill", "reheat": "Reheat", "dry": "Dry",
        },
        "done_one": "Basket {n} is done.",
        "done_one_rest": "Basket {n} is done. Basket {m} still has {min} min left.",
        "done_both": "Both baskets are done.",
        "done_whole": "Done!",
    },
}


def _left(state: FryerState) -> int | None:
    if state.cook_status in (None, AirFryerCookStatus.STANDBY):
        return None
    total = state.total_time_remaining
    return total if total is not None else state.cook_time_remaining


@dataclass
class _Activity:
    """One live activity we have started."""

    tag: str
    kind: str  # basket_1 / basket_2 / both / whole
    members: tuple[int, ...]
    signature: tuple | None = None
    left: dict[int, int | None] = field(default_factory=dict)
    total: int = 0
    # Seen cooking (or waiting for Sync) at least once.
    ran: bool = False
    clear_unsub: CALLBACK_TYPE | None = None


class LiveActivityManager:
    """Start, update and end the live activities of all fryers."""

    def __init__(self, hass: HomeAssistant, entry: CosoriConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        # cid -> tag -> activity
        self._acts: dict[str, dict[str, _Activity]] = {}

    @property
    def enabled(self) -> bool:
        """Live activities switched on in the options."""
        return bool(self.entry.options.get(CONF_LIVE_ACTIVITY, DEFAULT_LIVE_ACTIVITY))

    @property
    def _t(self) -> dict[str, Any]:
        lang = "de" if (self.hass.config.language or "").startswith("de") else "en"
        return TEXTS[lang]

    def _service(self) -> str | None:
        target = str(self.entry.options.get(CONF_NOTIFY_TARGET, "") or "").strip()
        domain, _, service = target.partition(".")
        if domain == "notify" and service and self.hass.services.has_service(
            "notify", service
        ):
            return service
        return None

    @callback
    def async_shutdown(self) -> None:
        """Cancel pending removals."""
        for acts in self._acts.values():
            for act in acts.values():
                if act.clear_unsub:
                    act.clear_unsub()
                    act.clear_unsub = None

    async def async_process(self, fryers: dict[str, VeSyncFryer]) -> None:
        """Bring the activities in line with the new states (after every poll)."""
        from .coordinator import chamber_states  # noqa: PLC0415

        service = self._service() if self.enabled else None
        for cid, fryer in fryers.items():
            acts = self._acts.setdefault(cid, {})
            if service is None:
                # Switched off (or no usable target): remove what is still shown.
                for act in list(acts.values()):
                    if act.signature is not None and act.signature[0] != "done":
                        await self._async_clear(service, act, acts)
                    elif act.clear_unsub is None:
                        acts.pop(act.tag, None)
                continue
            states = {
                (1 if ch == AirFryerChamber.CHAMBER_1 else 2): st
                for ch, st in chamber_states(fryer)
            }
            try:
                await self._async_fryer(service, fryer, cid, states, acts)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Could not update the air fryer live activity")

    def _groups(
        self, fryer: VeSyncFryer, states: dict[int, FryerState]
    ) -> dict[str, tuple[str, tuple[int, ...]]]:
        from .coordinator import is_cooking  # noqa: PLC0415

        active = [n for n, st in states.items() if is_cooking(st)]
        if not active:
            return {}
        work = fryer.work_chamber
        if work == AirFryerChamber.WHOLE:
            return {"whole": ("whole", (1,))}
        if work == AirFryerChamber.BOTH and len(states) == 2:
            return {"both": ("both", (1, 2))}
        return {f"basket_{n}": (f"basket_{n}", (n,)) for n in active}

    async def _async_fryer(
        self,
        service: str,
        fryer: VeSyncFryer,
        cid: str,
        states: dict[int, FryerState],
        acts: dict[str, _Activity],
    ) -> None:
        from .coordinator import ended_naturally  # noqa: PLC0415

        groups = self._groups(fryer, states)
        name = fryer.device_name.strip()

        # Activities that are no longer running: done or ended by hand.
        for key, act in list(acts.items()):
            if act.signature is not None and act.signature[0] == "done":
                if act.kind in groups:  # a new cook in the same basket
                    if act.clear_unsub:
                        act.clear_unsub()
                    acts.pop(key)
                continue
            if act.kind in groups:
                continue
            natural = act.ran and any(
                ended_naturally(states[n].cook_status, act.left.get(n), act.total)
                for n in act.members
                if n in states
            )
            if natural:
                await self._async_done(service, fryer, name, act, states, groups, acts)
            else:
                await self._async_clear(service, act, acts)

        # Running activities: start or update.
        for kind, (_, members) in groups.items():
            tag = f"{DOMAIN}_{cid}_{kind}"
            act = acts.get(kind)
            if act is None:
                act = acts[kind] = _Activity(tag=tag, kind=kind, members=members)
            await self._async_running(service, fryer, name, act, states)

    def _title(self, name: str, act: _Activity) -> str:
        t = self._t
        if act.kind == "whole":
            part = t["whole"]
        elif act.kind == "both":
            part = t["both"]
        else:
            part = t["basket"].format(n=act.members[0])
        return f"{name} · {part}"

    def _line(self, fryer: VeSyncFryer, state: FryerState, *, with_status: bool) -> str:
        from .sensor import _mode  # noqa: PLC0415

        t = self._t
        parts = []
        mode = _mode(fryer, state)
        if mode:
            parts.append(t["modes"].get(mode, mode))
        if state.cook_set_temp:
            parts.append(f"{int(state.cook_set_temp)} °C")
        if with_status and state.cook_status in t["status"]:
            parts.append(t["status"][state.cook_status])
        return " · ".join(parts)

    async def _async_running(
        self,
        service: str,
        fryer: VeSyncFryer,
        name: str,
        act: _Activity,
        states: dict[int, FryerState],
    ) -> None:
        from .sensor import _finish  # noqa: PLC0415

        members = [n for n in act.members if n in states]
        lefts = {n: _left(states[n]) for n in members}
        act.left = lefts
        t = self._t

        if act.kind == "both":
            lines = []
            for n in members:
                line = self._line(fryer, states[n], with_status=False)
                status = states[n].cook_status
                if status != AirFryerCookStatus.COOKING and status in t["status"]:
                    line += f" ({t['status'][status]})"
                lines.append(f"{n}: {line}")
            message = "\n".join(lines)
        else:
            message = self._line(fryer, states[members[0]], with_status=True)

        total = max((states[n].cook_set_time or 0) for n in members)
        act.total = int(total)
        left = max((v or 0) for v in lefts.values()) if lefts else 0
        finishes = [_finish(states[n]) for n in members]
        finish = max((f for f in finishes if f is not None), default=None)
        running = any(states[n].cook_status in RUNNING for n in members)
        if running:
            act.ran = True

        data: dict[str, Any] = {
            "tag": act.tag,
            "live_update": True,
            "silent": True,
            "alert_once": True,
            "notification_icon": ICON,
            "notification_icon_color": COLOR_RUN,
            "color": COLOR_RUN,
            "progress_bar_color": COLOR_RUN,
            "progress_bar_direction": "increasing",
        }
        elapsed = None
        if total > 0:
            elapsed = max(0, min(total, total - left))
            data["progress"] = int(elapsed)
            data["progress_max"] = int(total)
        if running and finish is not None:
            data["chronometer"] = True
            data["when"] = int(finish.timestamp())
            data["when_relative"] = False
            data["critical_text"] = finish.astimezone(
                dt_util.get_default_time_zone()
            ).strftime("%H:%M")

        signature = (
            "run",
            message,
            running,
            int(finish.timestamp()) // 20 if finish else None,
            (elapsed // PROGRESS_STEP_SECONDS) if elapsed is not None else None,
        )
        if signature == act.signature:
            return
        act.signature = signature
        await self._async_send(
            service, {"title": self._title(name, act), "message": message, "data": data}
        )

    async def _async_done(
        self,
        service: str,
        fryer: VeSyncFryer,
        name: str,
        act: _Activity,
        states: dict[int, FryerState],
        groups: dict[str, tuple[str, tuple[int, ...]]],
        acts: dict[str, _Activity],
    ) -> None:
        t = self._t
        if act.kind == "whole":
            message = t["done_whole"]
        elif act.kind == "both":
            message = t["done_both"]
        else:
            n = act.members[0]
            m = 2 if n == 1 else 1
            other = states.get(m)
            other_left = _left(other) if other is not None else None
            if other is not None and other.cook_status in RUNNING and other_left:
                message = t["done_one_rest"].format(
                    n=n, m=m, min=math.ceil(other_left / 60)
                )
            else:
                message = t["done_one"].format(n=n)
        total = act.total or 1
        data = {
            "tag": act.tag,
            "live_update": True,
            "silent": False,
            "notification_icon": ICON,
            "notification_icon_color": COLOR_DONE,
            "color": COLOR_DONE,
            "progress_bar_color": COLOR_DONE,
            "progress": total,
            "progress_max": total,
        }
        act.signature = ("done",)
        await self._async_send(
            service, {"title": self._title(name, act), "message": message, "data": data}
        )

        @callback
        def _remove(_now: Any) -> None:
            act.clear_unsub = None
            if acts.get(act.kind) is act and act.signature == ("done",):
                acts.pop(act.kind, None)
                self.hass.async_create_task(
                    self._async_send(
                        self._service() or service,
                        {"message": "clear_notification", "data": {"tag": act.tag}},
                    )
                )

        act.clear_unsub = async_call_later(self.hass, DONE_LINGER_SECONDS, _remove)

    async def _async_clear(
        self, service: str | None, act: _Activity, acts: dict[str, _Activity]
    ) -> None:
        acts.pop(act.kind, None)
        if act.clear_unsub:
            act.clear_unsub()
            act.clear_unsub = None
        service = service or self._service()
        if service:
            await self._async_send(
                service, {"message": "clear_notification", "data": {"tag": act.tag}}
            )

    async def _async_send(self, service: str, payload: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(
                "notify", service, payload, blocking=True
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Live activity push via notify.%s failed", service)
