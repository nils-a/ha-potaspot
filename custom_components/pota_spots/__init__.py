"""The POTA Spots integration."""

from __future__ import annotations

import logging
from pathlib import Path
from types import MappingProxyType

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .config_flow import clean_filter
from .const import (
    CARD_FILENAME,
    CARD_URL_BASE,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUBENTRY_FILTER,
)
from .coordinator import PotaSpotsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.EVENT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PotaConfigEntry = ConfigEntry[PotaSpotsCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dashboard card and load it in the frontend."""
    await _async_migrate_v1_entries(hass)

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{CARD_URL_BASE}/{CARD_FILENAME}", str(card_path), True)]
    )
    # Version in the URL so browsers pick up a new card after an update.
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILENAME}?v={integration.version}")
    return True


async def _async_migrate_v1_entries(hass: HomeAssistant) -> None:
    """Merge old entries (one per filter, each polling) into one hub with filter subentries.

    Runs before any entry is set up. Old entities are removed; the filters keep
    their names, so the new entity IDs are derived from the same names.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    old = [e for e in entries if e.version == 1]
    if not old:
        return

    hub = next((e for e in entries if e.version >= 2), None)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for entry in old:
        subentry = ConfigSubentry(
            data=MappingProxyType(clean_filter(dict(entry.options))),
            subentry_type=SUBENTRY_FILTER,
            title=entry.title,
            unique_id=None,
        )
        if hub is None:
            # The first old entry becomes the hub.
            hub = entry
            for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
                ent_reg.async_remove(entity.entity_id)
            for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
                dev_reg.async_remove_device(device.id)
            hass.config_entries.async_update_entry(
                entry,
                version=2,
                title=DEFAULT_NAME,
                options={
                    CONF_SCAN_INTERVAL: entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                },
            )
            hass.config_entries.async_add_subentry(entry, subentry)
        else:
            hass.config_entries.async_add_subentry(hub, subentry)
            await hass.config_entries.async_remove(entry.entry_id)
        _LOGGER.info("Migrated POTA Spots entry '%s' to a filter of the hub", subentry.title)


async def async_setup_entry(hass: HomeAssistant, entry: PotaConfigEntry) -> bool:
    """Set up POTA Spots from a config entry."""
    coordinator = PotaSpotsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Also fires when filters (subentries) are added, edited or removed.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: PotaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PotaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
