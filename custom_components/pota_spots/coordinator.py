"""Data coordinator for POTA Spots."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_URL,
    BANDS,
    CONF_BANDS,
    CONF_MAX_AGE,
    CONF_MODES,
    CONF_PARKS,
    CONF_PROGRAMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_AGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_SPOT,
    MIN_SCAN_INTERVAL,
    SUBENTRY_FILTER,
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


def parse_spot_time(value: Any) -> datetime | None:
    """Parse POTA's spotTime (UTC, usually without offset)."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        freq = float(raw.get("frequency"))
    except (TypeError, ValueError):
        freq = None
    reference = str(raw.get("reference") or "").upper()
    spot_time = parse_spot_time(raw.get("spotTime"))
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
        "spot_time": spot_time.isoformat() if spot_time else raw.get("spotTime"),
        "spotter": raw.get("spotter"),
        "comments": raw.get("comments"),
        "source": raw.get("source"),
    }


class SpotFilter:
    """One filter subentry: decides which spots belong to it."""

    def __init__(self, subentry: ConfigSubentry) -> None:
        data = subentry.data
        self.subentry_id = subentry.subentry_id
        self.title = subentry.title
        self.bands = parse_list(data.get(CONF_BANDS))
        self.modes = parse_list(data.get(CONF_MODES))
        self.programs = parse_list(data.get(CONF_PROGRAMS))
        self.parks = parse_list(data.get(CONF_PARKS))
        self.max_age = max(0, int(data.get(CONF_MAX_AGE, DEFAULT_MAX_AGE)))
        # One service device per filter so entity IDs get the filter name as prefix.
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://pota.app/#/",
        )

    def matches(self, spot: dict[str, Any], now: datetime) -> bool:
        if self.max_age:
            spot_time = parse_spot_time(spot["spot_time"])
            if spot_time is None or spot_time < now - timedelta(minutes=self.max_age):
                return False
        if self.parks and spot["reference"] not in self.parks:
            return False
        if self.programs and spot["program"] not in self.programs:
            return False
        if self.bands and (spot["band"] or "").upper() not in self.bands:
            return False
        if self.modes and spot["mode"] not in self.modes:
            return False
        return True


class PotaSpotsCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Polls the POTA API once and applies every filter subentry locally.

    `data` maps subentry_id -> matching spots (newest first).
    """

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
        self.filters: dict[str, SpotFilter] = {
            subentry_id: SpotFilter(subentry)
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_FILTER
        }
        self._seen: set[Any] | None = None
        # subentry_id -> spots that appeared with the last update
        self.new_spots: dict[str, list[dict[str, Any]]] = {}

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
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
            if s["id"] is not None
        ]
        spots.sort(key=lambda s: s["spot_time"] or "", reverse=True)

        # First fetch: don't announce everything that is already there.
        new_ids = (
            set() if self._seen is None else {s["id"] for s in spots} - self._seen
        )
        self._seen = {s["id"] for s in spots}

        now = dt_util.utcnow()
        result: dict[str, list[dict[str, Any]]] = {}
        self.new_spots = {}
        for subentry_id, spot_filter in self.filters.items():
            matching = [s for s in spots if spot_filter.matches(s, now)]
            result[subentry_id] = matching
            self.new_spots[subentry_id] = [s for s in matching if s["id"] in new_ids]
            for spot in self.new_spots[subentry_id]:
                self.hass.bus.async_fire(
                    EVENT_NEW_SPOT, {**spot, "entry": spot_filter.title}
                )
        return result
