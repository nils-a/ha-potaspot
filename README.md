# POTA Spots for Home Assistant

A HACS integration that polls the [Parks on the Air](https://parksontheair.com) spots (`api.pota.app`) and reports new spots.

DO NOT USE THIS INTEGRATION IT IS TOTALLY UNTESTED!

## Installation

1. HACS → Custom repositories → add this repo as an *Integration*.
2. Install `POTA Spots` and restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **POTA Spots**.

(Manual: copy `custom_components/pota_spots` to `config/custom_components/`.)

## Configuration

| Option | Description |
|---|---|
| Update interval | Minutes, minimum 1, default 3 |
| Bands | e.g. `20m`, `40m` (empty = all) |
| Modes | e.g. `SSB`, `CW`, `FT8` (empty = all, custom values allowed) |
| Programs | Country prefix of the park reference, comma-separated, e.g. `DL, US` |
| Parks | Park references, comma-separated, e.g. `DE-0001, K-1234` |

Different filters are combined with AND; multiple values within one filter are combined with OR.
You can add the integration **multiple times**, e.g. once for "all DL spots on 20m" and once for a single park. Change the settings later via *Configure*.

## Entities (per entry)

- `sensor.<name>_active_spots` – number of currently active matching spots; attributes `spots` (list, max. 50), `latest_spot` and the active filters.
- `event.<name>_new_spot` – fires for every new spot; the spot data is in the event attributes.
- Bus event `pota_spots_new_spot` with the same data (`activator`, `reference`, `park_name`, `frequency_khz`, `band`, `mode`, `comments`, `entry`, …).

Spots that already exist at startup/reload are **not** reported as new.
Note: every re-spot of an activator gets a new spot ID on POTA and therefore counts as a new spot.

## Example automation

```yaml
automation:
  - alias: Notify on POTA spot
    triggers:
      - trigger: event
        event_type: pota_spots_new_spot
        event_data:
          entry: POTA Spots
    actions:
      - action: notify.notify
        data:
          title: "POTA: {{ trigger.event.data.activator }}"
          message: >
            {{ trigger.event.data.reference }} {{ trigger.event.data.park_name }}
            – {{ trigger.event.data.frequency_khz }} kHz
            {{ trigger.event.data.mode }} ({{ trigger.event.data.band }})
```
