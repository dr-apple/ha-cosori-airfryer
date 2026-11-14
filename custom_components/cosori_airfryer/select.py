"""Selects for the cook settings of the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .actions import (
    default_duration_min,
    default_mode,
    default_temperature,
    mode_keys,
    supported_chamber_options,
)
from .coordinator import CosoriConfigEntry, CosoriCoordinator
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = []
    for fryer in coordinator.fryers.values():
        if fryer.is_dual_chamber:
            entities.append(ChamberSelect(coordinator, fryer))
        entities.append(ModeSelect(coordinator, fryer))
    async_add_entities(entities)


class _SettingSelect(CosoriEntity, SelectEntity):
    """A select that edits the stored start settings."""

    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        """Follow changes made by the other setting entities."""
        await super().async_added_to_hass()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )


class ChamberSelect(_SettingSelect):
    """Basket that is edited and started (Korb 1, Korb 2, ganzer Korb)."""

    _attr_translation_key = "chamber"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_chamber")
        self._attr_options = [
            o for o in supported_chamber_options(fryer) if o != "both"
        ]

    @property
    def current_option(self) -> str:
        """Return the selected basket."""
        return self.settings.chamber

    async def async_select_option(self, option: str) -> None:
        """Select a basket (the whole basket has no Sync/Match)."""
        self.settings.chamber = option
        if option == "whole":
            self.settings.link = "off"
        self.settings.notify()


class ModeSelect(_SettingSelect):
    """Cook program of the selected basket."""

    _attr_translation_key = "mode"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_mode")
        self._attr_options = mode_keys(fryer)
        for per in self.settings.per.values():
            if per.mode not in self._attr_options:
                per.mode = default_mode(fryer)

    @property
    def current_option(self) -> str | None:
        """Return the program of the selected basket."""
        return self.settings.current.mode

    async def async_select_option(self, option: str) -> None:
        """Select a program and load its default temperature and time."""
        cur = self.settings.current
        cur.mode = option
        cur.temperature = default_temperature(self.fryer, option)
        cur.duration_min = default_duration_min(self.fryer, option)
        self.settings.notify()
