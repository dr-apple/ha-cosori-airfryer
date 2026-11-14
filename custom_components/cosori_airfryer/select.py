"""Selects for the cook settings of the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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


class _SettingSelect(CosoriEntity, SelectEntity, RestoreEntity):
    """A select that stores a start setting."""

    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        """Restore the last value and follow changes from other entities."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self.options:
            self._restore(last.state)
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    def _restore(self, value: str) -> None:
        raise NotImplementedError


class ChamberSelect(_SettingSelect):
    """Which basket the start button uses."""

    _attr_translation_key = "chamber"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_chamber")
        self._attr_options = supported_chamber_options(fryer)

    def _restore(self, value: str) -> None:
        self.settings.chamber = value

    @property
    def current_option(self) -> str:
        """Return the selected chamber."""
        return self.settings.chamber

    async def async_select_option(self, option: str) -> None:
        """Select a chamber."""
        self.settings.chamber = option
        self.settings.notify()


class ModeSelect(_SettingSelect):
    """Cook mode used by the start button."""

    _attr_translation_key = "mode"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_mode")
        self._attr_options = mode_keys(fryer)
        if self.settings.mode is None:
            self.settings.mode = default_mode(fryer)

    def _restore(self, value: str) -> None:
        self.settings.mode = value

    @property
    def current_option(self) -> str | None:
        """Return the selected mode."""
        return self.settings.mode

    async def async_select_option(self, option: str) -> None:
        """Select a mode and load its default temperature and time."""
        self.settings.mode = option
        self.settings.temperature = default_temperature(self.fryer, option)
        self.settings.duration_min = default_duration_min(self.fryer, option)
        self.settings.notify()
