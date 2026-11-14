"""Sync / Match switches (the fryer's coupling buttons)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .coordinator import CosoriConfigEntry, CosoriCoordinator
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches for dual-basket fryers."""
    coordinator = entry.runtime_data
    async_add_entities(
        LinkSwitch(coordinator, fryer, link)
        for fryer in coordinator.fryers.values()
        if fryer.is_dual_chamber
        for link in ("sync", "match")
    )


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
