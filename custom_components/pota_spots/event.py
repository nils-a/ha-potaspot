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
    coordinator = entry.runtime_data
    for subentry_id in coordinator.filters:
        async_add_entities(
            [PotaNewSpotEvent(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


class PotaNewSpotEvent(EventEntity):
    """Triggers once per new spot; spot details are in the event attributes."""

    _attr_has_entity_name = True
    _attr_name = "New spot"
    _attr_icon = "mdi:radio-handheld"
    _attr_event_types = [EVENT_TYPE]
    _attr_should_poll = False

    def __init__(self, coordinator: PotaSpotsCoordinator, subentry_id: str) -> None:
        self._coordinator = coordinator
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{subentry_id}_new_spot"
        self._attr_device_info = coordinator.filters[subentry_id].device_info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        new_spots = self._coordinator.new_spots.get(self._subentry_id, [])
        for spot in new_spots:
            self._trigger_event(EVENT_TYPE, spot)
        if new_spots:
            self.async_write_ha_state()
