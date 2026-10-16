"""Data coordinator for POTA Spots."""

from __future__ import annotations

from datetime import timedelta
import logging
import re
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL,
    BANDS,
    CONF_BANDS,
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_SPOT,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def parse_list(value: Any) -> set[str]:
    """Turn 'DL, us;K-1234' (or a list) into an upper-case set."""
    if not value:
        return set()
    if isinstance(value, str):
        items = re.split(r"[,;\s]+", value)
    else:
        items = list(value)
    return {str(i).strip().upper() for i in items if str(i).strip()}


def band_for(freq_khz: float | None) -> str | None:
    """Return the band name for a frequency in kHz."""
    if freq_khz is None:
        return None
    for name, (low, high) in BANDS.items():
        if low <= freq_khz <= high:
            return name
    return None


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        freq = float(raw.get("frequency"))
    except (TypeError, ValueError):
        freq = None
    reference = str(raw.get("reference") or "").upper()
    return {
        "id": raw.get("spotId"),
        "activator": raw.get("activator"),
        "frequency_khz": freq,
        "band": band_for(freq),
        "mode": (raw.get("mode") or "").upper(),
        "reference": reference,
        "program": reference.split("-")[0] if "-" in reference else "",
        "park_name": raw.get("name"),
        "location": raw.get("locationDesc"),
        "grid": raw.get("grid6") or raw.get("grid4"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "spot_time": raw.get("spotTime"),
        "spotter": raw.get("spotter"),
        "comments": raw.get("comments"),
        "source": raw.get("source"),
    }


class PotaSpotsCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Polls the POTA API and applies the configured filters."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = max(
            MIN_SCAN_INTERVAL,
            int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            config_entry=entry,
            update_interval=timedelta(minutes=minutes),
        )
        opts = entry.options
        self._bands = parse_list(opts.get(CONF_BANDS))
        self._modes = parse_list(opts.get(CONF_MODES))
        self._programs = parse_list(opts.get(CONF_PROGRAMS))
        self._parks = parse_list(opts.get(CONF_PARKS))
        self._seen: set[Any] | None = None
        self.new_spots: list[dict[str, Any]] = []

    def _matches(self, spot: dict[str, Any]) -> bool:
        if self._parks and spot["reference"] not in self._parks:
            return False
        if self._programs and spot["program"] not in self._programs:
            return False
        if self._bands and (spot["band"] or "").upper() not in self._bands:
            return False
        if self._modes and spot["mode"] not in self._modes:
            return False
        return True

    async def _async_update_data(self) -> list[dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                API_URL, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                raw_spots = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Error fetching POTA spots: {err}") from err

        if not isinstance(raw_spots, list):
            raise UpdateFailed("Unexpected response from POTA API")

        spots = [
            s
            for s in (
                _normalize(r) for r in raw_spots if isinstance(r, dict) and not r.get("invalid")
            )
            if s["id"] is not None and self._matches(s)
        ]
        spots.sort(key=lambda s: s["spot_time"] or "", reverse=True)

        current_ids = {s["id"] for s in spots}
        if self._seen is None:
            # First fetch: don't announce everything that is already there.
            self.new_spots = []
        else:
            self.new_spots = [s for s in spots if s["id"] not in self._seen]
        self._seen = current_ids

        for spot in self.new_spots:
            self.hass.bus.async_fire(
                EVENT_NEW_SPOT, {**spot, "entry": self.config_entry.title}
            )
        return spots
