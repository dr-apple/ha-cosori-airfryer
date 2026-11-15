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

# Options: push notifications when a basket is done.
CONF_NOTIFY_ENABLED: Final = "notify_enabled"
CONF_NOTIFY_TARGET: Final = "notify_target"
CONF_NOTIFY_APART: Final = "notify_apart"
CONF_NOTIFY_TOGETHER: Final = "notify_together"
CONF_NOTIFY_TOLERANCE: Final = "notify_tolerance"
CONF_NOTIFY_BASKET_1: Final = "notify_basket_1"
CONF_NOTIFY_BASKET_2: Final = "notify_basket_2"
DEFAULT_NOTIFY_ENABLED: Final = False
DEFAULT_NOTIFY_APART: Final = True
DEFAULT_NOTIFY_TOGETHER: Final = True
DEFAULT_NOTIFY_TOLERANCE: Final = 1
DEFAULT_NOTIFY_BASKET: Final = True
# Live Activity (iOS) / Live Update (Android) while cooking, same target.
CONF_LIVE_ACTIVITY: Final = "live_activity"
DEFAULT_LIVE_ACTIVITY: Final = False

SERVICE_START_COOKING: Final = "start_cooking"
SERVICE_END_COOKING: Final = "end_cooking"
