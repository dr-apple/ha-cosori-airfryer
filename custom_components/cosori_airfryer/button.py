"""Buttons for the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.const import AirFryerChamber

from .actions import async_end_cooking, async_start_cooking
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

    async def async_press(self) -> None:
        """Start the cook."""
        s = self.settings
        chamber = s.chamber if self.fryer.is_dual_chamber else "chamber_1"
        await async_start_cooking(
            self.coordinator, self.fryer, chamber, s.mode, s.temperature, s.duration_min
        )


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
