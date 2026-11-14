"""Numbers for the cook settings of the Cosori Airfryer integration."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import VeSyncFryer

from .actions import (
    default_duration_min,
    default_temperature,
    temp_limits,
    time_limits_min,
)
from .coordinator import CosoriConfigEntry, CosoriCoordinator
from .entity import CosoriEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    for fryer in coordinator.fryers.values():
        entities.append(TemperatureNumber(coordinator, fryer))
        entities.append(DurationNumber(coordinator, fryer))
    async_add_entities(entities)


class _SettingNumber(CosoriEntity, NumberEntity):
    """A setting of the selected basket; limits follow its program."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _field: str

    def _limits(self) -> tuple[int, int, int]:
        raise NotImplementedError

    def _default(self) -> int:
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Follow changes made by the other setting entities."""
        await super().async_added_to_hass()
        self.settings.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.settings.listeners.remove(self.async_write_ha_state)
        )

    @property
    def native_min_value(self) -> float:
        """Minimum for the program."""
        return self._limits()[0]

    @property
    def native_max_value(self) -> float:
        """Maximum for the program."""
        return self._limits()[1]

    @property
    def native_step(self) -> float:
        """Step for the program."""
        return self._limits()[2]

    @property
    def native_value(self) -> float | None:
        """Return the stored value (program default if unset), clamped."""
        value = getattr(self.settings.current, self._field)
        if value is None:
            value = self._default()
        lo, hi, _ = self._limits()
        return min(max(value, lo), hi)

    async def async_set_native_value(self, value: float) -> None:
        """Store a new value for the selected basket."""
        setattr(self.settings.current, self._field, int(value))
        self.settings.notify()


class TemperatureNumber(_SettingNumber):
    """Cook temperature of the selected basket."""

    _attr_translation_key = "temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _field = "temperature"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_temperature")

    def _limits(self) -> tuple[int, int, int]:
        return temp_limits(self.fryer, self.settings.current.mode)

    def _default(self) -> int:
        return default_temperature(self.fryer, self.settings.current.mode)


class DurationNumber(_SettingNumber):
    """Cook time (minutes) of the selected basket."""

    _attr_translation_key = "duration"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _field = "duration_min"

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "start_duration")

    def _limits(self) -> tuple[int, int, int]:
        return time_limits_min(self.fryer, self.settings.current.mode)

    def _default(self) -> int:
        return default_duration_min(self.fryer, self.settings.current.mode)
