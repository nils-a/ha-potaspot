"""Sensor platform for POTA Spots."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PotaConfigEntry
from .const import (
    CONF_BANDS,
    CONF_MAX_AGE,
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    DEFAULT_MAX_AGE,
    MAX_SPOTS_ATTRIBUTE,
)
from .coordinator import PotaSpotsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PotaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    for subentry_id in coordinator.filters:
        async_add_entities(
            [PotaSpotCountSensor(coordinator, entry, subentry_id)],
            config_subentry_id=subentry_id,
        )


class PotaSpotCountSensor(CoordinatorEntity[PotaSpotsCoordinator], SensorEntity):
    """Number of currently active spots matching one filter."""

    _attr_has_entity_name = True
    _attr_name = "Active spots"
    _attr_icon = "mdi:radio-tower"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "spots"
    _unrecorded_attributes = frozenset({"spots"})

    def __init__(
        self, coordinator: PotaSpotsCoordinator, entry: PotaConfigEntry, subentry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._subentry = entry.subentries[subentry_id]
        self._attr_unique_id = f"{subentry_id}_spots"
        self._attr_device_info = coordinator.filters[subentry_id].device_info

    @property
    def _spots(self) -> list[dict[str, Any]]:
        return (self.coordinator.data or {}).get(self._subentry.subentry_id, [])

    @property
    def native_value(self) -> int:
        return len(self._spots)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        opts = self._subentry.data
        spots = self._spots
        return {
            "filter_max_age_minutes": opts.get(CONF_MAX_AGE, DEFAULT_MAX_AGE),
            "filter_bands": opts.get(CONF_BANDS),
            "filter_modes": opts.get(CONF_MODES),
            "filter_programs": opts.get(CONF_PROGRAMS),
            "filter_parks": opts.get(CONF_PARKS),
            "latest_spot": spots[0] if spots else None,
            "spots": spots[:MAX_SPOTS_ATTRIBUTE],
        }
