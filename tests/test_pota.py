import json
from datetime import timedelta
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.pota_spots.const import API_URL, DOMAIN

LIVE = json.loads((Path(__file__).parent / "fixtures" / "spots.json").read_text())
FILTER = {"max_age": 10, "bands": [], "modes": [], "programs": "", "parks": ""}


def _spot(i, minutes_ago, **kw):
    s = dict(LIVE[i % len(LIVE)])
    s["spotId"] = 1000 + i
    s["spotTime"] = (dt_util.utcnow() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S")
    s.update(kw)
    return s


def _sub(title, **data):
    return {"subentry_type": "filter", "title": title, "data": {**FILTER, **data}, "unique_id": None}


async def _setup(hass, aioclient_mock, spots, filters=None):
    aioclient_mock.get(API_URL, json=spots)
    entry = MockConfigEntry(
        domain=DOMAIN, title="POTA Spots", version=2,
        options={"scan_interval": 3},
        subentries_data=filters or [_sub("POTA Spots")],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _tick(hass, freezer, minutes=4):
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_age_filter(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock, [_spot(0, 2), _spot(1, 9), _spot(2, 30)])
    st = hass.states.get("sensor.pota_spots_active_spots")
    assert st.state == "2"
    assert st.attributes["filter_max_age_minutes"] == 10
    spots = st.attributes["spots"]
    assert [s["id"] for s in spots] == [1000, 1001]  # newest first
    assert spots[0]["spot_time"].endswith("+00:00")
    assert spots[0]["park_name"]


async def test_no_age_limit(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock, [_spot(0, 2), _spot(2, 300)], [_sub("POTA Spots", max_age=0)])
    assert hass.states.get("sensor.pota_spots_active_spots").state == "2"


async def test_live_data_does_not_crash(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock, LIVE, [_sub("POTA Spots", max_age=0)])
    assert hass.states.get("sensor.pota_spots_active_spots").state == str(
        len([s for s in LIVE if not s.get("invalid")])
    )


async def test_two_filters_one_request(hass: HomeAssistant, aioclient_mock, freezer):
    spots = [
        _spot(0, 1, frequency="14070", reference="DE-0001"),
        _spot(1, 1, frequency="7030", reference="US-1"),
    ]
    await _setup(hass, aioclient_mock, spots, [_sub("DL 20m", bands=["20m"], programs="DE"), _sub("Everything")])
    assert aioclient_mock.call_count == 1
    assert hass.states.get("sensor.dl_20m_active_spots").state == "1"
    assert hass.states.get("sensor.everything_active_spots").state == "2"
    await _tick(hass, freezer)
    assert aioclient_mock.call_count == 2


async def test_new_spot_event_per_filter(hass: HomeAssistant, aioclient_mock, freezer: FrozenDateTimeFactory):
    await _setup(hass, aioclient_mock, [_spot(0, 2)], [_sub("Park", parks="DE-0001"), _sub("Everything")])
    events = async_capture_events(hass, "pota_spots_new_spot")

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=[
        _spot(0, 2),
        _spot(5, 0, activator="DL1ABC", reference="DE-0001"),
        _spot(6, 0, reference="US-0001"),
    ])
    await _tick(hass, freezer)

    by_filter = sorted((e.data["entry"], e.data["reference"]) for e in events)
    assert by_filter == [("Everything", "DE-0001"), ("Everything", "US-0001"), ("Park", "DE-0001")]
    assert hass.states.get("event.park_new_spot").attributes["activator"] == "DL1ABC"
    assert hass.states.get("event.everything_new_spot").attributes["event_type"] == "new_spot"


async def test_card_is_served(hass: HomeAssistant, aioclient_mock, hass_client):
    await _setup(hass, aioclient_mock, [])
    client = await hass_client()
    resp = await client.get("/pota_spots/pota-spots-card.js")
    assert resp.status == 200
    assert "pota-spots-card" in await resp.text()
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
    assert "/pota_spots/pota-spots-card.js?v=0.1.1" in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_config_flow_creates_hub_with_default_filter(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL, json=[_spot(0, 1)])
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"scan_interval": 2})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.options == {"scan_interval": 2}
    assert [s.title for s in entry.subentries.values()] == ["All spots"]
    assert hass.states.get("sensor.all_spots_active_spots").state == "1"

    # a second hub is refused
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_interval(hass: HomeAssistant, aioclient_mock):
    entry = await _setup(hass, aioclient_mock, [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 7})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=7)


async def test_add_and_edit_filter(hass: HomeAssistant, aioclient_mock):
    entry = await _setup(hass, aioclient_mock, [_spot(0, 1, frequency="14070"), _spot(1, 1, frequency="7030")])
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "filter"), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Only 40m", "max_age": 10, "bands": ["40m"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.only_40m_active_spots").state == "1"
    assert hass.states.get("sensor.pota_spots_active_spots").state == "2"

    sub = next(s for s in entry.subentries.values() if s.title == "Only 40m")
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Only 40m", "max_age": 10, "bands": ["40m", "20m"]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.only_40m_active_spots").state == "2"

    # removing a filter removes its entities
    assert hass.config_entries.async_remove_subentry(entry, sub.subentry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.only_40m_active_spots") is None


async def test_migrate_two_v1_entries(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL, json=[_spot(0, 1, frequency="14070"), _spot(1, 1, frequency="7030")])
    ent_reg = er.async_get(hass)
    old_ids = set()
    for title, opts in [("DL", {"scan_interval": 5, "bands": ["20m"]}), ("All", {"scan_interval": 1})]:
        e = MockConfigEntry(domain=DOMAIN, title=title, version=1, options=opts)
        e.add_to_hass(hass)
        ent_reg.async_get_or_create("sensor", DOMAIN, f"{e.entry_id}_spots", config_entry=e)
        old_ids.add(f"{e.entry_id}_spots")

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    hub = entries[0]
    assert hub.version == 2 and hub.title == "POTA Spots"
    assert hub.options == {"scan_interval": 5}
    assert sorted(s.title for s in hub.subentries.values()) == ["All", "DL"]
    assert hub.state is config_entries.ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 1
    assert hass.states.get("sensor.dl_active_spots").state == "1"
    assert hass.states.get("sensor.all_active_spots").state == "2"
    assert not [x for x in ent_reg.entities.values() if x.unique_id in old_ids]
