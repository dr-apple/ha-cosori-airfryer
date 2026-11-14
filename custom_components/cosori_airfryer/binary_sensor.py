"""Binary sensors for the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.const import AirFryerChamber

from .coordinator import CosoriConfigEntry, CosoriCoordinator, chamber_states
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for fryer in coordinator.fryers.values():
        entities.append(OnlineSensor(coordinator, fryer))
        entities.extend(
            RunningSensor(coordinator, fryer, chamber)
            for chamber, _ in chamber_states(fryer)
        )
    async_add_entities(entities)


class RunningSensor(CosoriEntity, BinarySensorEntity):
    """On while a chamber is heating or cooking."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: CosoriCoordinator,
        fryer: VeSyncFryer,
        chamber: AirFryerChamber,
    ) -> None:
        """Initialize."""
        suffix = f"chamber_{int(chamber)}"
        super().__init__(coordinator, fryer, f"running_{suffix}")
        self._chamber = chamber
        self._attr_translation_key = (
            f"running_{suffix}" if fryer.is_dual_chamber else "running"
        )

    @property
    def is_on(self) -> bool | None:
        """Return True while cooking."""
        state = self.fryer.get_chamber_state(self._chamber)
        return None if state is None else state.is_running


class OnlineSensor(CosoriEntity, BinarySensorEntity):
    """Cloud connection of the fryer."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "online")

    @property
    def is_on(self) -> bool:
        """Return True if VeSync reports the fryer online."""
        return self.fryer.state.connection_status == "online"
