"""Sync / Match switches (the fryer's coupling buttons)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .actions import default_duration_min, default_temperature
from .coordinator import CosoriConfigEntry, CosoriCoordinator, StartSettings
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches for dual-basket fryers."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        LinkSwitch(coordinator, fryer, link)
        for fryer in coordinator.fryers.values()
        if fryer.is_dual_chamber
        for link in ("sync", "match")
    ]
    entities.extend(PlanSwitch(coordinator, f) for f in coordinator.fryers.values())
    async_add_entities(entities)


class LinkSwitch(CosoriEntity, SwitchEntity):
    """Sync: own settings per basket, both finish together. Match: same settings."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: CosoriCoordinator, fryer: VeSyncFryer, link: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, link)
        self._link = link
        self._attr_translation_key = link

    async def async_added_to_hass(self) -> None:
        """Follow changes made by the other setting entities."""
        await super().async_added_to_hass()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        """Return True if this coupling is active."""
        return self.settings.link == self._link

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn this coupling on (the other one goes off)."""
        self.settings.link = self._link
        if self.settings.chamber == "whole":
            self.settings.chamber = "chamber_1"
        self.settings.notify()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the coupling off."""
        if self.settings.link == self._link:
            self.settings.link = "off"
            self.settings.notify()


class PlanSwitch(CosoriEntity, SwitchEntity):
    """Planned start armed. Turning it on freezes the current settings."""

    _attr_translation_key = "plan"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "plan")

    async def async_added_to_hass(self) -> None:
        """Follow plan changes."""
        await super().async_added_to_hass()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        """Return True while a start is planned."""
        return self.settings.plan_armed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Planned start time and the frozen settings."""
        s = self.settings
        start = self.coordinator.plan_start_time(self.fryer.cid)
        snap = StartSettings.from_cook_dict(s.plan_snapshot or s.cook_dict())
        attrs: dict[str, Any] = {
            "start_time": start.isoformat() if start else None,
            "plan_time": s.plan_at.isoformat() if s.plan_at else None,
            "plan_type": s.plan_type,
            "chamber": snap.chamber,
            "link": snap.link,
        }
        for n, per in snap.per.items():
            attrs[f"chamber_{n}"] = {
                "mode": per.mode,
                "temperature": per.temperature
                if per.temperature is not None
                else default_temperature(self.fryer, per.mode),
                "duration": per.duration_min
                if per.duration_min is not None
                else default_duration_min(self.fryer, per.mode),
            }
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm the plan."""
        self.coordinator.async_arm_plan(self.fryer.cid)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel the plan."""
        self.coordinator.async_disarm_plan(self.fryer.cid)
