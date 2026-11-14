"""Constants for the Cosori Airfryer integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from pyvesync.const import AirFryerChamber

DOMAIN: Final = "cosori_airfryer"

CONF_COUNTRY_CODE: Final = "country_code"
DEFAULT_COUNTRY_CODE: Final = "DE"

# Poll faster while something is cooking, slower when idle (cloud API).
SCAN_INTERVAL_ACTIVE: Final = timedelta(seconds=15)
SCAN_INTERVAL_IDLE: Final = timedelta(seconds=60)

# Delay before re-polling after a command, so the cloud reflects the change.
REFRESH_DELAY: Final = 3

# Chamber options (select / service) -> pyvesync chamber.
CHAMBER_OPTIONS: Final[dict[str, AirFryerChamber]] = {
    "chamber_1": AirFryerChamber.CHAMBER_1,
    "chamber_2": AirFryerChamber.CHAMBER_2,
    "whole": AirFryerChamber.WHOLE,
    "both": AirFryerChamber.BOTH,
}
CHAMBER_TO_OPTION: Final[dict[AirFryerChamber, str]] = {
    v: k for k, v in CHAMBER_OPTIONS.items()
}

ATTR_CHAMBER: Final = "chamber"
ATTR_MODE: Final = "mode"
ATTR_TEMPERATURE: Final = "temperature"
ATTR_DURATION: Final = "duration"

SERVICE_START_COOKING: Final = "start_cooking"
SERVICE_END_COOKING: Final = "end_cooking"
