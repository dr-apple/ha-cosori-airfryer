"""Cooking commands shared by the button entities and the services."""

from __future__ import annotations

import dataclasses
import logging

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.const import AirFryerModeConfig
from pyvesync.utils.errors import VeSyncError

from .const import CHAMBER_OPTIONS, DOMAIN, REFRESH_DELAY
from .coordinator import CosoriCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_SECONDS = 60
DEFAULT_MAX_SECONDS = 3600
DEFAULT_STEP_SECONDS = 60


def mode_keys(fryer: VeSyncFryer) -> list[str]:
    """Return the cook mode keys of a fryer (e.g. 'airfry', 'roast')."""
    return [str(key) for key in fryer.cook_modes]


def default_mode(fryer: VeSyncFryer) -> str:
    """Return the default cook mode key."""
    default_cfg = fryer.get_cook_mode(None)
    for key, cfg in fryer.cook_modes.items():
        if cfg is default_cfg:
            return str(key)
    return mode_keys(fryer)[0]


def mode_config(fryer: VeSyncFryer, mode: str | None) -> AirFryerModeConfig:
    """Return the mode config, falling back to the default mode."""
    cfg = fryer.get_cook_mode(mode) if mode else None
    if cfg is None:
        cfg = fryer.get_cook_mode(default_mode(fryer))
    assert cfg is not None
    return cfg


def temp_limits(fryer: VeSyncFryer, mode: str | None) -> tuple[int, int, int]:
    """Return (min, max, step) temperature for a mode in the fryer's unit."""
    limits = mode_config(fryer, mode).limits(fryer.temp_unit)
    return limits.min_temp, limits.max_temp, limits.step


def time_limits_min(fryer: VeSyncFryer, mode: str | None) -> tuple[int, int, int]:
    """Return (min, max, step) cook time for a mode in minutes."""
    limits = mode_config(fryer, mode).time_limits
    if limits is None:
        lo, hi, step = DEFAULT_MIN_SECONDS, DEFAULT_MAX_SECONDS, DEFAULT_STEP_SECONDS
    else:
        lo, hi, step = limits.min_seconds, limits.max_seconds, limits.step_seconds
    return max(1, lo // 60), hi // 60, max(1, step // 60)


def default_temperature(fryer: VeSyncFryer, mode: str | None) -> int:
    """Return the app's default temperature for a mode."""
    return mode_config(fryer, mode).to_recipe(fryer.temp_unit).target_temp


def default_duration_min(fryer: VeSyncFryer, mode: str | None) -> int:
    """Return the app's default cook time for a mode in minutes."""
    return max(1, mode_config(fryer, mode).cook_time // 60)


def _snap(value: int, lo: int, hi: int, step: int) -> int:
    """Clamp to [lo, hi] and round to the step grid starting at lo."""
    value = min(max(value, lo), hi)
    return lo + round((value - lo) / step) * step


def supported_chamber_options(fryer: VeSyncFryer) -> list[str]:
    """Return the chamber option keys this fryer supports."""
    return [
        key
        for key, chamber in CHAMBER_OPTIONS.items()
        if chamber in fryer.supported_chambers
    ]


async def async_start_cooking(
    coordinator: CosoriCoordinator,
    fryer: VeSyncFryer,
    chamber: str,
    mode: str | None,
    temperature: int | None,
    duration_min: int | None,
) -> None:
    """Start a cook on the fryer."""
    if chamber not in CHAMBER_OPTIONS or CHAMBER_OPTIONS[
        chamber
    ] not in fryer.supported_chambers:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_chamber",
            translation_placeholders={"chamber": chamber},
        )
    if mode and fryer.get_cook_mode(mode) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_mode",
            translation_placeholders={
                "mode": mode,
                "modes": ", ".join(mode_keys(fryer)),
            },
        )
    mode = mode or default_mode(fryer)
    t_lo, t_hi, t_step = temp_limits(fryer, mode)
    d_lo, d_hi, d_step = time_limits_min(fryer, mode)
    temp = _snap(
        temperature if temperature is not None else default_temperature(fryer, mode),
        t_lo,
        t_hi,
        t_step,
    )
    minutes = _snap(
        duration_min if duration_min is not None else default_duration_min(fryer, mode),
        d_lo,
        d_hi,
        d_step,
    )
    recipe = dataclasses.replace(
        mode_config(fryer, mode).to_recipe(fryer.temp_unit),
        target_temp=temp,
        cook_time=minutes * 60,
    )
    _LOGGER.debug(
        "Start %s: chamber=%s mode=%s temp=%s time=%s min",
        fryer.device_name,
        chamber,
        mode,
        temp,
        minutes,
    )
    try:
        ok = await fryer.set_mode_from_recipe(recipe, chamber=CHAMBER_OPTIONS[chamber])
    except VeSyncError as err:
        raise HomeAssistantError(f"VeSync error: {err}") from err
    if not ok:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_failed"
        )
    coordinator.async_update_listeners()
    _schedule_refresh(coordinator)


async def async_end_cooking(
    coordinator: CosoriCoordinator, fryer: VeSyncFryer, chamber: str
) -> None:
    """End cooking in a chamber ('both' ends everything)."""
    target = CHAMBER_OPTIONS.get(chamber)
    if target is None or target not in fryer.supported_chambers:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_chamber",
            translation_placeholders={"chamber": chamber},
        )
    try:
        ok = await fryer.end(target)
    except VeSyncError as err:
        raise HomeAssistantError(f"VeSync error: {err}") from err
    if not ok:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_failed"
        )
    coordinator.async_update_listeners()
    _schedule_refresh(coordinator)


def _schedule_refresh(coordinator: CosoriCoordinator) -> None:
    """Re-poll shortly after a command."""
    from . import async_delayed_refresh  # noqa: PLC0415

    coordinator.config_entry.async_create_background_task(
        coordinator.hass,
        async_delayed_refresh(coordinator, REFRESH_DELAY),
        "cosori_airfryer_refresh",
    )

