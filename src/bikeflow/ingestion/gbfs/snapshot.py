"""Snapshot de station_information: full refresh, nao CDC.

Diferente de station_status (muda a cada poll, por isso CDC + Pub/Sub),
station_information muda raramente (nome, capacidade, lat/lon de uma
estacao). bronze.station_information guarda so' o estado ATUAL (truncate +
insert a cada execucao) - o historico de mudancas fica a cargo do dbt
snapshot (Fase 3.5), nao desta camada.
"""

from __future__ import annotations

import uuid
from typing import Any

from bikeflow.common import warehouse
from bikeflow.ingestion.gbfs.client import fetch_station_information

_CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS bronze"
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bronze.station_information (
    station_id    VARCHAR,
    short_name    VARCHAR,
    name          VARCHAR,
    lat           DOUBLE,
    lon           DOUBLE,
    capacity      BIGINT,
    _ingested_at  TIMESTAMP NOT NULL DEFAULT now(),
    _batch_id     VARCHAR
)
"""


def load_station_information(
    batch_id: str | None = None,
    stations: list[dict[str, Any]] | None = None,
) -> int:
    """Busca (ou usa `stations` injetado, para teste) e substitui o snapshot
    em bronze.station_information. Devolve quantas estacoes carregou.
    """
    batch_id = batch_id or uuid.uuid4().hex
    if stations is None:
        stations = fetch_station_information()

    rows = [
        (
            station["station_id"],
            station.get("short_name"),
            station.get("name"),
            station.get("lat"),
            station.get("lon"),
            station.get("capacity"),
            batch_id,
        )
        for station in stations
    ]

    with warehouse.get_connection() as conn:
        conn.execute(_CREATE_SCHEMA)
        conn.execute(_CREATE_TABLE)
        # DELETE + INSERT precisam ser atomicos: sem transacao explicita, uma
        # interrupcao no meio (timeout, crash) deixa a tabela truncada com so'
        # parte do snapshot novo - corrompida ate' a proxima carga completa.
        # executemany (1 chamada) tambem e' bem mais rapido que fazer INSERT
        # linha a linha num loop Python (~2500 estacoes).
        conn.begin()
        try:
            conn.execute("DELETE FROM bronze.station_information")
            conn.executemany(
                """
                INSERT INTO bronze.station_information
                    (station_id, short_name, name, lat, lon, capacity, _batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
    return len(stations)
