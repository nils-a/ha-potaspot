"""Config flow for POTA Spots.

One hub entry polls the API; every filter is a config subentry of that hub.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
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
    CONF_MAX_AGE,
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_FILTER_NAME,
    DEFAULT_MAX_AGE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SUBENTRY_FILTER,
)


def _hub_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
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
        }
    )


def _filter_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_FILTER_NAME)
            ): str,
            vol.Required(
                CONF_MAX_AGE,
                default=defaults.get(CONF_MAX_AGE, DEFAULT_MAX_AGE),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=1440,
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
    )


def _clean_hub(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_SCAN_INTERVAL: max(MIN_SCAN_INTERVAL, int(user_input[CONF_SCAN_INTERVAL]))
    }


def clean_filter(user_input: dict[str, Any]) -> dict[str, Any]:
    """Filter data as stored in a subentry (name is the subentry title)."""
    return {
        CONF_MAX_AGE: max(0, int(user_input.get(CONF_MAX_AGE, DEFAULT_MAX_AGE))),
        CONF_BANDS: list(user_input.get(CONF_BANDS) or []),
        CONF_MODES: list(user_input.get(CONF_MODES) or []),
        CONF_PROGRAMS: user_input.get(CONF_PROGRAMS) or "",
        CONF_PARKS: user_input.get(CONF_PARKS) or "",
    }


class PotaSpotsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the hub entry (only one allowed, see manifest)."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={},
                options=_clean_hub(user_input),
                # Start with a catch-all filter so there is something to see.
                subentries=[
                    {
                        "subentry_type": SUBENTRY_FILTER,
                        "title": DEFAULT_FILTER_NAME,
                        "data": clean_filter({}),
                        "unique_id": None,
                    }
                ],
            )

        return self.async_show_form(step_id="user", data_schema=_hub_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PotaSpotsOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_FILTER: PotaFilterSubentryFlow}


class PotaSpotsOptionsFlow(OptionsFlow):
    """Edit the update interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean_hub(user_input))

        return self.async_show_form(
            step_id="init", data_schema=_hub_schema(dict(self.config_entry.options))
        )


class PotaFilterSubentryFlow(ConfigSubentryFlow):
    """Add or edit a filter."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME], data=clean_filter(user_input)
            )

        return self.async_show_form(step_id="user", data_schema=_filter_schema({}))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_NAME],
                data=clean_filter(user_input),
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_filter_schema({CONF_NAME: subentry.title, **subentry.data}),
        )
