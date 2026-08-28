"""Testes unitarios do cliente GBFS. Sem rede real."""

from __future__ import annotations

import pytest
import responses

from bikeflow.ingestion.gbfs.client import (
    GBFS_DISCOVERY_URL,
    discover_feed_url,
    fetch_station_information,
    fetch_station_status,
)

_DISCOVERY_BODY = {
    "data": {
        "en": {
            "feeds": [
                {
                    "name": "station_information",
                    "url": "https://gbfs.lyft.com/x/station_information.json",
                },
                {"name": "station_status", "url": "https://gbfs.lyft.com/x/station_status.json"},
            ]
        }
    }
}


@responses.activate
def test_discover_feed_url_resolves_by_name():
    responses.add(responses.GET, GBFS_DISCOVERY_URL, json=_DISCOVERY_BODY, status=200)

    url = discover_feed_url("station_status")

    assert url == "https://gbfs.lyft.com/x/station_status.json"


@responses.activate
def test_discover_feed_url_raises_when_feed_missing():
    responses.add(responses.GET, GBFS_DISCOVERY_URL, json=_DISCOVERY_BODY, status=200)

    with pytest.raises(FileNotFoundError):
        discover_feed_url("free_bike_status")


@responses.activate
def test_fetch_station_status_returns_station_list():
    responses.add(responses.GET, GBFS_DISCOVERY_URL, json=_DISCOVERY_BODY, status=200)
    responses.add(
        responses.GET,
        "https://gbfs.lyft.com/x/station_status.json",
        json={
            "data": {
                "stations": [
                    # station_id mistura UUID e numero legado no mesmo feed - real.
                    {"station_id": "1822663031356509142", "num_bikes_available": 3},
                    {
                        "station_id": "90b141b9-c39f-4a26-a32d-08c7d1474d52",
                        "num_bikes_available": 0,
                    },
                ]
            },
            "last_updated": 1787882874,
        },
        status=200,
    )

    stations = fetch_station_status()

    assert stations == [
        {"station_id": "1822663031356509142", "num_bikes_available": 3},
        {"station_id": "90b141b9-c39f-4a26-a32d-08c7d1474d52", "num_bikes_available": 0},
    ]


@responses.activate
def test_fetch_station_information_returns_station_list():
    responses.add(responses.GET, GBFS_DISCOVERY_URL, json=_DISCOVERY_BODY, status=200)
    responses.add(
        responses.GET,
        "https://gbfs.lyft.com/x/station_information.json",
        json={
            "data": {
                "stations": [
                    {
                        "station_id": "dd482585-3028-453f-a98d-55019db9b26c",
                        "short_name": "3460.01",
                        "name": "2 Ave & 36 St",
                        "capacity": 43,
                    }
                ]
            }
        },
        status=200,
    )

    stations = fetch_station_information()

    assert stations == [
        {
            "station_id": "dd482585-3028-453f-a98d-55019db9b26c",
            "short_name": "3460.01",
            "name": "2 Ave & 36 St",
            "capacity": 43,
        }
    ]
