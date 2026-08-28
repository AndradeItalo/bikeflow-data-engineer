"""Testes unitarios do snapshot de station_information. So' toca um DuckDB temporario."""

from __future__ import annotations

import pytest

from bikeflow.common import warehouse
from bikeflow.ingestion.gbfs.snapshot import load_station_information

pytestmark = pytest.mark.usefixtures("isolated_duckdb")

STATIONS = [
    {
        "station_id": "dd482585-3028-453f-a98d-55019db9b26c",
        "short_name": "3460.01",
        "name": "2 Ave & 36 St",
        "lat": 40.657,
        "lon": -74.008,
        "capacity": 43,
    },
    {
        "station_id": "1822663031356509142",
        "short_name": "3034.02",
        "name": "Matthews Ct & Coney Island Ave",
        "lat": 40.65,
        "lon": -73.96,
        "capacity": 21,
    },
]


def test_load_station_information_inserts_rows():
    count = load_station_information(batch_id="batch-1", stations=STATIONS)

    assert count == 2
    with warehouse.get_connection() as conn:
        rows = conn.execute(
            "SELECT station_id, short_name, capacity FROM bronze.station_information "
            "ORDER BY station_id"
        ).fetchall()
    assert rows == [
        ("1822663031356509142", "3034.02", 21),
        ("dd482585-3028-453f-a98d-55019db9b26c", "3460.01", 43),
    ]


def test_load_station_information_replaces_previous_snapshot():
    load_station_information(batch_id="batch-1", stations=STATIONS)

    # segunda carga: so' 1 estacao, capacidade mudou - simula uma estacao
    # removida e outra com capacidade alterada
    count = load_station_information(
        batch_id="batch-2",
        stations=[{**STATIONS[0], "capacity": 50}],
    )

    assert count == 1
    with warehouse.get_connection() as conn:
        rows = conn.execute(
            "SELECT station_id, capacity FROM bronze.station_information"
        ).fetchall()
    assert rows == [("dd482585-3028-453f-a98d-55019db9b26c", 50)]
