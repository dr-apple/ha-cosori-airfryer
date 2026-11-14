"""Buttons for the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.const import AirFryerChamber

from .actions import (
    async_end_cooking,
    async_start_from_settings,
    default_duration_min,
    default_temperature,
)
from .const import CHAMBER_TO_OPTION
from .coordinator import CosoriConfigEntry, CosoriCoordinator, chamber_states
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = []
    for fryer in coordinator.fryers.values():
        entities.append(StartButton(coordinator, fryer))
        if fryer.is_dual_chamber:
            entities.extend(
                EndButton(coordinator, fryer, chamber)
                for chamber, _ in chamber_states(fryer)
            )
            entities.append(EndButton(coordinator, fryer, AirFryerChamber.BOTH))
        else:
            entities.append(EndButton(coordinator, fryer, AirFryerChamber.CHAMBER_1))
    async_add_entities(entities)


class StartButton(CosoriEntity, ButtonEntity):
    """Start cooking with the configured settings."""

    _attr_translation_key = "start"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start")

    async def async_added_to_hass(self) -> None:
        """Expose the current start settings as attributes."""
        await super().async_added_to_hass()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Settings per basket (used by the dashboard card)."""
        s = self.settings
        attrs: dict = {"chamber": s.chamber, "link": s.link}
        for n, per in s.per.items():
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

    async def async_press(self) -> None:
        """Start the cook with the stored settings."""
        await async_start_from_settings(self.coordinator, self.fryer)


class EndButton(CosoriEntity, ButtonEntity):
    """End cooking in a chamber (or everything)."""

    def __init__(
        self,
        coordinator: CosoriCoordinator,
        fryer: VeSyncFryer,
        chamber: AirFryerChamber,
    ) -> None:
        """Initialize."""
        option = CHAMBER_TO_OPTION[chamber]
        super().__init__(coordinator, fryer, f"end_{option}")
        self._option = option
        self._attr_translation_key = (
            f"end_{option}" if fryer.is_dual_chamber else "end"
        )

    async def async_press(self) -> None:
        """End the cook."""
        await async_end_cooking(self.coordinator, self.fryer, self._option)
