"""Constants for the POTA Spots integration."""

from __future__ import annotations

DOMAIN = "pota_spots"

API_URL = "https://api.pota.app/spot/activator"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_BANDS = "bands"
CONF_MODES = "modes"
CONF_PROGRAMS = "programs"
CONF_PARKS = "parks"
CONF_MAX_AGE = "max_age"

MIN_SCAN_INTERVAL = 1
DEFAULT_SCAN_INTERVAL = 3
# Minutes since the last spot; 0 = no age limit.
DEFAULT_MAX_AGE = 10
DEFAULT_NAME = "POTA Spots"
DEFAULT_FILTER_NAME = "All spots"

# Each filter is a config subentry of the single hub entry.
SUBENTRY_FILTER = "filter"

EVENT_NEW_SPOT = "pota_spots_new_spot"

CARD_URL_BASE = "/pota_spots"
CARD_FILENAME = "pota-spots-card.js"

# Band name -> (lower kHz, upper kHz)
BANDS: dict[str, tuple[float, float]] = {
    "160m": (1800, 2000),
    "80m": (3500, 4000),
    "60m": (5250, 5450),
    "40m": (7000, 7300),
    "30m": (10100, 10150),
    "20m": (14000, 14350),
    "17m": (18068, 18168),
    "15m": (21000, 21450),
    "12m": (24890, 24990),
    "10m": (28000, 29700),
    "6m": (50000, 54000),
    "2m": (144000, 148000),
    "70cm": (420000, 450000),
}

COMMON_MODES = ["SSB", "CW", "FT8", "FT4", "AM", "FM", "RTTY", "JS8", "PSK31", "DIGITAL"]

# Attribute list is capped so the state attributes stay small.
MAX_SPOTS_ATTRIBUTE = 50
