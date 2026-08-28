"""Testes unitarios da logica de CDC do poller. So' toca um DuckDB temporario."""

from __future__ import annotations

import pytest

from bikeflow.ingestion.gbfs.poller import _filter_changed_stations

pytestmark = pytest.mark.usefixtures("isolated_duckdb")


def test_first_call_treats_every_station_as_changed():
    stations = [
        {"station_id": "a", "last_reported": 100},
        {"station_id": "b", "last_reported": 200},
    ]

    changed = _filter_changed_stations(stations)

    assert changed == stations


def test_second_call_with_same_data_returns_nothing():
    stations = [{"station_id": "a", "last_reported": 100}]
    _filter_changed_stations(stations)

    changed = _filter_changed_stations(stations)

    assert changed == []


def test_only_stations_with_new_last_reported_are_returned():
    _filter_changed_stations(
        [
            {"station_id": "a", "last_reported": 100},
            {"station_id": "b", "last_reported": 200},
        ]
    )

    changed = _filter_changed_stations(
        [
            {"station_id": "a", "last_reported": 100},  # nao mudou
            {"station_id": "b", "last_reported": 999},  # mudou
        ]
    )

    assert changed == [{"station_id": "b", "last_reported": 999}]
