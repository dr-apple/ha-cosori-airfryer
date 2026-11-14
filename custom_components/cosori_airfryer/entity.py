"""Base entity for the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .const import DOMAIN
from .coordinator import CosoriCoordinator


class CosoriEntity(CoordinatorEntity[CosoriCoordinator]):
    """An entity belonging to one air fryer."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CosoriCoordinator, fryer: VeSyncFryer, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.fryer = fryer
        self._attr_unique_id = f"{fryer.cid}_{key}"
        connections = set()
        if fryer.mac_id:
            connections.add((CONNECTION_NETWORK_MAC, fryer.mac_id.lower()))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, fryer.cid)},
            connections=connections,
            name=fryer.device_name,
            manufacturer="Cosori",
            model=getattr(fryer, "model_name", None) or fryer.device_type,
            model_id=fryer.device_type,
            sw_version=fryer.current_firm_version,
        )

    @property
    def settings(self):
        """Return the start settings of this fryer."""
        return self.coordinator.settings[self.fryer.cid]
