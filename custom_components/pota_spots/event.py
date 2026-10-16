"""Event platform: fires whenever a new matching spot appears."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PotaConfigEntry
from .coordinator import PotaSpotsCoordinator

EVENT_TYPE = "new_spot"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PotaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PotaNewSpotEvent(entry.runtime_data, entry)])


class PotaNewSpotEvent(EventEntity):
    """Triggers once per new spot; spot details are in the event attributes."""

    _attr_has_entity_name = True
    _attr_name = "New spot"
    _attr_icon = "mdi:radio-handheld"
    _attr_event_types = [EVENT_TYPE]
    _attr_should_poll = False

    def __init__(self, coordinator: PotaSpotsCoordinator, entry: PotaConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_new_spot"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        for spot in self._coordinator.new_spots:
            self._trigger_event(EVENT_TYPE, spot)
        if self._coordinator.new_spots:
            self.async_write_ha_state()
