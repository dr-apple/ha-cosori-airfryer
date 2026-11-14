"""Planned start time of the Cosori Airfryer integration."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .coordinator import CosoriConfigEntry, CosoriCoordinator
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the plan time entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        PlanTime(coordinator, fryer) for fryer in coordinator.fryers.values()
    )


def _tomorrow_nine() -> datetime:
    now = dt_util.now()
    nine = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if nine <= now:
        nine += timedelta(days=1)
    return nine


class PlanTime(CosoriEntity, DateTimeEntity):
    """Time of the planned start (or finish, see the plan type)."""

    _attr_translation_key = "plan_time"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "plan_time")

    async def async_added_to_hass(self) -> None:
        """Default to the next 09:00 and follow changes."""
        await super().async_added_to_hass()
        if self.settings.plan_at is None:
            self.settings.plan_at = _tomorrow_nine()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the plan time."""
        return self.settings.plan_at

    async def async_set_value(self, value: datetime) -> None:
        """Set the plan time; an armed plan is rescheduled with it."""
        s = self.settings
        old = s.plan_at
        s.plan_at = value.replace(second=0, microsecond=0)
        if s.plan_armed:
            try:
                self.coordinator.async_arm_plan(self.fryer.cid)
            except Exception:
                s.plan_at = old
                raise
            return
        s.notify()
