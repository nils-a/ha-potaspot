# POTA Spots for Home Assistant

A HACS integration that polls the [Parks on the Air](https://parksontheair.com) spots (`api.pota.app`) and reports new spots.

DO NOT USE THIS INTEGRATION IT IS TOTALLY UNTESTED!

## Installation

1. HACS → Custom repositories → add this repo as an *Integration*.
2. Install `POTA Spots` and restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **POTA Spots**.

(Manual: copy `custom_components/pota_spots` to `config/custom_components/`.)

## Configuration

The integration is set up **once**. It polls the POTA API once per update interval and
applies any number of **filters** locally, so adding filters does not add API requests.

| Integration option (*Configure*) | Description |
|---|---|
| Update interval | Minutes, minimum 1, default 3 |

Setup creates a first filter "All spots". Add more filters via **Add filter** on the
integration page and edit one later via its ⋮ menu → *Reconfigure*.

| Filter option | Description |
|---|---|
| Name | Becomes the device name and the prefix of the entity IDs |
| Active within | Only spots from the last *n* minutes count as active, default 10 (`0` = no limit) |
| Bands | e.g. `20m`, `40m` (empty = all) |
| Modes | e.g. `SSB`, `CW`, `FT8` (empty = all, custom values allowed) |
| Programs | Country prefix of the park reference, comma-separated, e.g. `DL, US` |
| Parks | Park references, comma-separated, e.g. `DE-0001, K-1234` |

Within a filter, different options are combined with AND; multiple values within one option are combined with OR.
Example: one filter "DL 20m" (program `DL`, band `20m`) and one filter "Home park" (park `DE-0001`).

**Upgrading from 0.1.0:** existing entries (one per filter) are merged automatically into a
single integration entry, each old entry becoming a filter with the same name. The update
interval of the first entry is kept. The entities are recreated, so their history starts
fresh and you may need to adjust entity IDs in dashboards/automations.

## Entities (per filter)

Each filter is a device with:

- `sensor.<filter>_active_spots` – number of matching spots within the *Active within* window; attributes `spots` (list, newest first, max. 50), `latest_spot` and the filter settings. `spot_time` is an ISO timestamp in UTC.
- `event.<filter>_new_spot` – fires for every new matching spot; the spot data is in the event attributes.
- Bus event `pota_spots_new_spot` with the same data (`activator`, `reference`, `park_name`, `frequency_khz`, `band`, `mode`, `comments`, …); `entry` is the filter name. A spot matching several filters fires once per filter.

Spots that already exist at startup/reload are **not** reported as new.
Note: every re-spot of an activator gets a new spot ID on POTA and therefore counts as a new spot.

## Dashboard card

The integration ships its own card and loads it automatically (no extra resource needed).
Dashboard → Edit → Add card → search for **POTA Spots**, or in YAML:

```yaml
type: custom:pota-spots-card
entity: sensor.all_spots_active_spots
# optional:
title: POTA
max_rows: 20
show_comments: true
```

It lists age, activator (links to QRZ), park (links to pota.app), frequency, mode and band
of every spot in the sensor's `spots` attribute, newest first.
After updating the integration, reload the browser if the old card is still shown.

### Alternative: Markdown card

Without the custom card, a **Markdown card** with this content works too:

```jinja
{% set spots = state_attr('sensor.all_spots_active_spots', 'spots') or [] %}
{% if spots %}
| Age | Activator | Park | kHz | Mode |
|---|---|---|---|---|
{% for s in spots %}
| {{ ((now() - as_datetime(s.spot_time)).total_seconds() // 60) | int }} min | **{{ s.activator }}** | {{ s.reference }} – {{ s.park_name }} | {{ s.frequency_khz }} | {{ s.mode }} |
{% endfor %}
{% else %}
No active spots.
{% endif %}
```

The age column updates every minute; the list itself refreshes with the update interval.

## Example automation: specific activator or park

```yaml
automation:
  - alias: DL1ABC is on the air
    mode: single
    triggers:
      - trigger: event
        event_type: pota_spots_new_spot
    conditions:
      # starts with, so DL1ABC/P matches as well
      - condition: template
        value_template: "{{ trigger.event.data.activator.upper().startswith('DL1ABC') }}"
    actions:
      - action: notify.notify
        data:
          message: >
            {{ trigger.event.data.activator }} in {{ trigger.event.data.reference }}
            on {{ trigger.event.data.frequency_khz }} kHz {{ trigger.event.data.mode }}
      # every re-spot fires again – stay quiet for 30 minutes
      - delay: "00:30:00"
```

For an exact match you can also put `activator: DL1ABC` or `reference: DE-0001` directly under `event_data`.

## Example automation

```yaml
automation:
  - alias: Notify on POTA spot
    triggers:
      - trigger: event
        event_type: pota_spots_new_spot
        event_data:
          entry: All spots   # filter name
    actions:
      - action: notify.notify
        data:
          title: "POTA: {{ trigger.event.data.activator }}"
          message: >
            {{ trigger.event.data.reference }} {{ trigger.event.data.park_name }}
            – {{ trigger.event.data.frequency_khz }} kHz
            {{ trigger.event.data.mode }} ({{ trigger.event.data.band }})
```
