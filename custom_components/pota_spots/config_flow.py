"""Config flow for POTA Spots."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    BANDS,
    COMMON_MODES,
    CONF_BANDS,
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


def _filter_schema(defaults: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                max=120,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="min",
            )
        ),
        vol.Optional(
            CONF_BANDS, default=defaults.get(CONF_BANDS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(BANDS),
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_MODES, default=defaults.get(CONF_MODES, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=COMMON_MODES,
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_PROGRAMS, default=defaults.get(CONF_PROGRAMS, "")
        ): TextSelector(TextSelectorConfig()),
        vol.Optional(
            CONF_PARKS, default=defaults.get(CONF_PARKS, "")
        ): TextSelector(TextSelectorConfig()),
    }


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    out = dict(user_input)
    out[CONF_SCAN_INTERVAL] = max(MIN_SCAN_INTERVAL, int(out[CONF_SCAN_INTERVAL]))
    return out


class PotaSpotsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(
                title=name, data={}, options=_clean(user_input)
            )

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=DEFAULT_NAME): str, **_filter_schema({})}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return PotaSpotsOptionsFlow()


class PotaSpotsOptionsFlow(OptionsFlow):
    """Edit interval and filters."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(_filter_schema(dict(self.config_entry.options))),
        )
