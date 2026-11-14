"""Push notifications when a basket is done.

The fryer's two baskets can run with different times. This module watches the
polled states and, depending on the options, sends

* one message **per basket** when the baskets finish at different times
  ("apart": the other basket still has more than the tolerance left), and/or
* **one** message when both finish together or only one basket was used.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerCookStatus

from .const import (
    CONF_NOTIFY_APART,
    CONF_NOTIFY_BASKET_1,
    CONF_NOTIFY_BASKET_2,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_TOGETHER,
    CONF_NOTIFY_TOLERANCE,
    DEFAULT_NOTIFY_APART,
    DEFAULT_NOTIFY_BASKET,
    DEFAULT_NOTIFY_ENABLED,
    DEFAULT_NOTIFY_TOGETHER,
    DEFAULT_NOTIFY_TOLERANCE,
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

# A basket that drops straight to standby with more than this left was ended
# by hand (or the plug was pulled), not finished: no message.
NATURAL_END_SECONDS = 120

TEXTS = {
    "de": {
        "apart": "Korb {n} ist fertig. Korb {m} läuft noch {min} min.",
        "apart_last": "Korb {n} ist fertig.",
        "both": "Beide Körbe sind fertig.",
        "single": "Korb {n} ist fertig.",
    },
    "en": {
        "apart": "Basket {n} is done. Basket {m} still has {min} min left.",
        "apart_last": "Basket {n} is done.",
        "both": "Both baskets are done.",
        "single": "Basket {n} is done.",
    },
}


def remaining_seconds(state: FryerState) -> int | None:
    """Seconds left of a basket, or None when idle."""
    if state.cook_status in (None, AirFryerCookStatus.STANDBY):
        return None
    total = state.total_time_remaining
    return total if total is not None else state.cook_time_remaining


@dataclass
class _Track:
    """What we saw of a fryer at the last poll."""

    status: dict[int, AirFryerCookStatus | None] = field(default_factory=dict)
    remaining: dict[int, int | None] = field(default_factory=dict)
    # Basket 1/2 already got a per-basket message because the other one ran on.
    apart: bool = False
    # Basket whose own message was folded into a combined one.
    suppress: set[int] = field(default_factory=set)


class FinishNotifier:
    """Detect finished baskets and send the configured pushes."""

    def __init__(self, hass: HomeAssistant, entry: CosoriConfigEntry) -> None:
        """Initialize the notifier."""
        self.hass = hass
        self.entry = entry
        self._tracks: dict[str, _Track] = {}

    @property
    def _opts(self) -> dict[str, Any]:
        return dict(self.entry.options)

    def _text(self, key: str) -> str:
        lang = "de" if (self.hass.config.language or "").startswith("de") else "en"
        return TEXTS[lang][key]

    async def async_process(self, fryers: dict[str, VeSyncFryer]) -> None:
        """Look at the new states of all fryers (call after every poll)."""
        from .coordinator import chamber_states  # noqa: PLC0415

        for cid, fryer in fryers.items():
            states = {
                (1 if ch.name.endswith("1") else 2): st
                for ch, st in chamber_states(fryer)
            }
            track = self._tracks.get(cid)
            now_status = {n: st.cook_status for n, st in states.items()}
            now_remaining = {n: remaining_seconds(st) for n, st in states.items()}
            if track is None:  # first poll: only remember
                self._tracks[cid] = _Track(status=now_status, remaining=now_remaining)
                continue

            finished = [
                n
                for n, st in now_status.items()
                if track.status.get(n) in RUNNING and self._ended_naturally(
                    st, track.remaining.get(n)
                )
            ]
            try:
                await self._async_handle(fryer, track, states, finished)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Could not send the air fryer notification")

            if not any(st in RUNNING for st in now_status.values()):
                track.apart = False
                track.suppress.clear()
            track.status = now_status
            track.remaining = now_remaining

    @staticmethod
    def _ended_naturally(
        status: AirFryerCookStatus | None, previous_left: int | None
    ) -> bool:
        if status in DONE:
            return True
        if status in (None, AirFryerCookStatus.STANDBY):
            return previous_left is not None and previous_left <= NATURAL_END_SECONDS
        return False

    async def _async_handle(
        self,
        fryer: VeSyncFryer,
        track: _Track,
        states: dict[int, FryerState],
        finished: list[int],
    ) -> None:
        if not finished or not self._opts.get(CONF_NOTIFY_ENABLED, DEFAULT_NOTIFY_ENABLED):
            return
        opts = self._opts
        tolerance = int(opts.get(CONF_NOTIFY_TOLERANCE, DEFAULT_NOTIFY_TOLERANCE)) * 60
        want_apart = opts.get(CONF_NOTIFY_APART, DEFAULT_NOTIFY_APART)
        want_together = opts.get(CONF_NOTIFY_TOGETHER, DEFAULT_NOTIFY_TOGETHER)
        baskets_on = {
            1: opts.get(CONF_NOTIFY_BASKET_1, DEFAULT_NOTIFY_BASKET),
            2: opts.get(CONF_NOTIFY_BASKET_2, DEFAULT_NOTIFY_BASKET),
        }
        name = fryer.device_name.strip()

        # Both done in the same poll: they finished together.
        if len(finished) == 2:
            track.suppress.clear()
            if want_together:
                await self._async_send(fryer, name, self._text("both"), "both")
            return

        n = finished[0]
        m = 2 if n == 1 else 1
        if n in track.suppress:  # already announced together with the other
            track.suppress.discard(n)
            return
        other = states.get(m)
        other_running = other is not None and other.cook_status in RUNNING
        other_left = remaining_seconds(other) if other is not None else None

        if other_running and (other_left or 0) > tolerance:
            # Different times: this basket gets its own message.
            track.apart = True
            if want_apart and baskets_on[n]:
                minutes = math.ceil((other_left or 0) / 60)
                text = self._text("apart").format(n=n, m=m, min=minutes)
                await self._async_send(fryer, name, text, f"basket_{n}")
            return
        if other_running:
            # The other one is within the tolerance: one message for both.
            track.suppress.add(m)
            if want_together:
                await self._async_send(fryer, name, self._text("both"), "both")
            return
        if track.apart:
            # The earlier basket was announced alone, so announce this one too.
            track.apart = False
            if want_apart and baskets_on[n]:
                await self._async_send(
                    fryer, name, self._text("apart_last").format(n=n), f"basket_{n}"
                )
            return
        # The other basket was not in use: a single-basket cook.
        if want_together and baskets_on[n]:
            await self._async_send(
                fryer, name, self._text("single").format(n=n), f"basket_{n}"
            )

    async def _async_send(
        self, fryer: VeSyncFryer, title: str, message: str, tag: str
    ) -> None:
        target = str(self._opts.get(CONF_NOTIFY_TARGET, "") or "").strip()
        data = {"tag": f"{DOMAIN}_{fryer.cid}_{tag}"}
        domain, _, service = target.partition(".")
        if domain == "notify" and service:
            if self.hass.services.has_service("notify", service):
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": title, "message": message, "data": data},
                    blocking=True,
                )
                return
            if self.hass.states.get(target) is not None:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": target, "title": title, "message": message},
                    blocking=True,
                )
                return
            _LOGGER.warning(
                "Notification target %s does not exist, using a persistent "
                "notification",
                target,
            )
        persistent_notification.async_create(
            self.hass,
            message,
            title=title,
            notification_id=f"{DOMAIN}_{fryer.cid}_{tag}",
        )
