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
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    MAX_SPOTS_ATTRIBUTE,
)
from .coordinator import PotaSpotsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PotaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PotaSpotCountSensor(entry.runtime_data, entry)])


class PotaSpotCountSensor(CoordinatorEntity[PotaSpotsCoordinator], SensorEntity):
    """Number of currently active spots matching the filter."""

    _attr_has_entity_name = True
    _attr_name = "Active spots"
    _attr_icon = "mdi:radio-tower"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "spots"
    _unrecorded_attributes = frozenset({"spots"})

    def __init__(self, coordinator: PotaSpotsCoordinator, entry: PotaConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_spots"
        self._entry = entry

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        opts = self._entry.options
        spots = self.coordinator.data or []
        return {
            "filter_bands": opts.get(CONF_BANDS),
            "filter_modes": opts.get(CONF_MODES),
            "filter_programs": opts.get(CONF_PROGRAMS),
            "filter_parks": opts.get(CONF_PARKS),
            "latest_spot": spots[0] if spots else None,
            "spots": spots[:MAX_SPOTS_ATTRIBUTE],
        }
