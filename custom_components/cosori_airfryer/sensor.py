"""Sensors for the Cosori Airfryer integration."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyvesync.base_devices.fryer_base import FryerState, VeSyncFryer
from pyvesync.const import AirFryerChamber, AirFryerCookModes, AirFryerCookStatus

from .const import CHAMBER_TO_OPTION
from .coordinator import CosoriConfigEntry, CosoriCoordinator, chamber_states
from .entity import CosoriEntity


def _snake(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


STATUS_OPTIONS = [_snake(s.value) for s in AirFryerCookStatus]
MODE_OPTIONS = [str(m) for m in AirFryerCookModes]


def _status(state: FryerState) -> str:
    if state.cook_status is None:
        return "standby"
    return _snake(state.cook_status.value)


def _mode(fryer: VeSyncFryer, state: FryerState) -> str | None:
    if not state.cook_mode or state.cook_status in (None, AirFryerCookStatus.STANDBY):
        return None
    for key, cfg in fryer.cook_modes.items():
        if cfg.api_mode == state.cook_mode or str(key) == state.cook_mode:
            return str(key)
    snake = _snake(state.cook_mode)
    return snake if snake in MODE_OPTIONS else None


def _remaining(state: FryerState) -> int | None:
    if state.cook_status in (None, AirFryerCookStatus.STANDBY):
        return None
    total = state.total_time_remaining
    return total if total is not None else state.cook_time_remaining


def _finish(state: FryerState) -> datetime | None:
    """Finish time, anchored to the last poll so it does not jitter."""
    if state.cook_status not in (
        AirFryerCookStatus.COOKING,
        AirFryerCookStatus.HEATING,
        AirFryerCookStatus.HOLD,
    ):
        return None
    if state.last_timestamp is None:
        return None
    left = state.total_last_time
    if left is None:
        left = state.cook_last_time
    if left is None:
        return None
    return (state.last_timestamp + timedelta(seconds=left)).replace(microsecond=0)


def _active(state: FryerState) -> bool:
    return state.cook_status not in (None, AirFryerCookStatus.STANDBY)


@dataclass(frozen=True, kw_only=True)
class ChamberSensorDescription(SensorEntityDescription):
    """Describes a per-chamber sensor."""

    value_fn: Callable[[VeSyncFryer, FryerState], object]


CHAMBER_SENSORS: tuple[ChamberSensorDescription, ...] = (
    ChamberSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value_fn=lambda f, s: _status(s),
    ),
    ChamberSensorDescription(
        key="remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda f, s: _remaining(s),
    ),
    ChamberSensorDescription(
        key="finish",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda f, s: _finish(s),
    ),
    ChamberSensorDescription(
        key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=MODE_OPTIONS,
        value_fn=_mode,
    ),
    ChamberSensorDescription(
        key="set_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda f, s: s.cook_set_temp if _active(s) else None,
    ),
    ChamberSensorDescription(
        key="set_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda f, s: s.cook_set_time if _active(s) else None,
    ),
)

WORK_CHAMBER_OPTIONS = ["none", *CHAMBER_TO_OPTION.values()]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CosoriConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for fryer in coordinator.fryers.values():
        for chamber, _ in chamber_states(fryer):
            entities.extend(
                ChamberSensor(coordinator, fryer, chamber, desc)
                for desc in CHAMBER_SENSORS
            )
        if fryer.is_dual_chamber:
            entities.append(WorkChamberSensor(coordinator, fryer))
    async_add_entities(entities)


class ChamberSensor(CosoriEntity, SensorEntity):
    """A sensor for one chamber."""

    entity_description: ChamberSensorDescription

    def __init__(
        self,
        coordinator: CosoriCoordinator,
        fryer: VeSyncFryer,
        chamber: AirFryerChamber,
        description: ChamberSensorDescription,
    ) -> None:
        """Initialize."""
        suffix = f"chamber_{int(chamber)}"
        super().__init__(coordinator, fryer, f"{description.key}_{suffix}")
        self.entity_description = description
        self._chamber = chamber
        self._attr_translation_key = (
            f"{description.key}_{suffix}" if fryer.is_dual_chamber else description.key
        )

    @property
    def native_value(self):
        """Return the value."""
        state = self.fryer.get_chamber_state(self._chamber)
        if state is None:
            return None
        return self.entity_description.value_fn(self.fryer, state)

    @property
    def available(self) -> bool:
        """Available while the cloud says the fryer is online."""
        return super().available and self.fryer.state.connection_status != "offline"


class WorkChamberSensor(CosoriEntity, SensorEntity):
    """Which basket configuration is currently in use."""

    _attr_translation_key = "work_chamber"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = WORK_CHAMBER_OPTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CosoriCoordinator, fryer: VeSyncFryer) -> None:
        """Initialize."""
        super().__init__(coordinator, fryer, "work_chamber")

    @property
    def native_value(self) -> str:
        """Return the active chamber."""
        work = self.fryer.work_chamber
        return CHAMBER_TO_OPTION.get(work, "none") if work else "none"
