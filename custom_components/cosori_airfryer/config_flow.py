"""Config flow for the Cosori Airfryer integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError, VeSyncLoginError

from .const import (
    CONF_COUNTRY_CODE,
    CONF_LIVE_ACTIVITY,
    CONF_NOTIFY_APART,
    CONF_NOTIFY_BASKET_1,
    CONF_NOTIFY_BASKET_2,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_TOGETHER,
    CONF_NOTIFY_TOLERANCE,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_LIVE_ACTIVITY,
    DEFAULT_NOTIFY_APART,
    DEFAULT_NOTIFY_BASKET,
    DEFAULT_NOTIFY_ENABLED,
    DEFAULT_NOTIFY_TOGETHER,
    DEFAULT_NOTIFY_TOLERANCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_COUNTRY_CODE,
                default=defaults.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE),
            ): str,
        }
    )


class CosoriAirfryerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cosori Airfryer."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: push notifications."""
        return CosoriOptionsFlow()

    async def _async_try_login(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, int]:
        """Log in; return (error key, number of air fryers)."""
        manager = VeSync(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            country_code=user_input[CONF_COUNTRY_CODE].strip().upper(),
            session=async_get_clientsession(self.hass),
            time_zone=str(self.hass.config.time_zone),
        )
        try:
            await manager.login()
            await manager.get_devices()
        except VeSyncLoginError:
            return "invalid_auth", 0
        except (VeSyncError, TimeoutError):
            return "cannot_connect", 0
        except Exception:
            _LOGGER.exception("Unexpected error during VeSync login")
            return "unknown", 0
        return None, len(manager.devices.air_fryers)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the VeSync account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_COUNTRY_CODE] = user_input[CONF_COUNTRY_CODE].strip().upper()
            await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
            self._abort_if_unique_id_configured()
            error, count = await self._async_try_login(user_input)
            if error:
                errors["base"] = error
            elif count == 0:
                errors["base"] = "no_fryers"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """A Cosori device showed up on the network."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Credentials stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            error, _ = await self._async_try_login(data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )


class CosoriOptionsFlow(OptionsFlow):
    """Settings for the "basket done" push notifications."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the notification settings."""
        if user_input is not None:
            user_input[CONF_NOTIFY_TARGET] = user_input.get(
                CONF_NOTIFY_TARGET, ""
            ).strip()
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NOTIFY_ENABLED,
                    default=o.get(CONF_NOTIFY_ENABLED, DEFAULT_NOTIFY_ENABLED),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_NOTIFY_TARGET,
                    default=o.get(CONF_NOTIFY_TARGET, ""),
                ): TextSelector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY,
                    default=o.get(CONF_LIVE_ACTIVITY, DEFAULT_LIVE_ACTIVITY),
                ): BooleanSelector(),
                vol.Required(
                    CONF_NOTIFY_APART,
                    default=o.get(CONF_NOTIFY_APART, DEFAULT_NOTIFY_APART),
                ): BooleanSelector(),
                vol.Required(
                    CONF_NOTIFY_TOGETHER,
                    default=o.get(CONF_NOTIFY_TOGETHER, DEFAULT_NOTIFY_TOGETHER),
                ): BooleanSelector(),
                vol.Required(
                    CONF_NOTIFY_TOLERANCE,
                    default=o.get(CONF_NOTIFY_TOLERANCE, DEFAULT_NOTIFY_TOLERANCE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=30,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NOTIFY_BASKET_1,
                    default=o.get(CONF_NOTIFY_BASKET_1, DEFAULT_NOTIFY_BASKET),
                ): BooleanSelector(),
                vol.Required(
                    CONF_NOTIFY_BASKET_2,
                    default=o.get(CONF_NOTIFY_BASKET_2, DEFAULT_NOTIFY_BASKET),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
