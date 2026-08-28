"""Poller GBFS: publica no Pub/Sub so' as estacoes cujo last_reported mudou.

Sem isso, pollar ~2500 estacoes a cada 2 min publicando tudo sempre daria
~1,8 milhao de mensagens/dia (falha B4 do PLAN.md - volume de streaming nao
dimensionado). meta.station_status_seen guarda o ultimo last_reported visto
por station_id entre uma execucao e outra - mesmo padrao de estado
persistente do ingestion_manifest (Fase 1), so' que aqui a mudanca e' o
proprio campo last_reported do GBFS, nao um hash calculado por nos.
"""

from __future__ import annotations

from typing import Any

from bikeflow.common import messaging, warehouse
from bikeflow.ingestion.gbfs.client import fetch_station_status

_CREATE_SEEN_TABLE = """
CREATE TABLE IF NOT EXISTS meta.station_status_seen (
    station_id    VARCHAR PRIMARY KEY,
    last_reported BIGINT NOT NULL,
    seen_at       TIMESTAMP NOT NULL DEFAULT now()
)
"""


def _filter_changed_stations(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Devolve so' as estacoes cujo last_reported mudou desde a ultima chamada.

    Na primeira chamada (tabela vazia), toda estacao conta como mudada - e'
    o bootstrap correto do CDC, nao um bug.
    """
    with warehouse.get_connection() as conn:
        conn.execute(_CREATE_SEEN_TABLE)
        seen = dict(
            conn.execute(
                "SELECT station_id, last_reported FROM meta.station_status_seen"
            ).fetchall()
        )

        changed = [
            station
            for station in stations
            if seen.get(station["station_id"]) != station["last_reported"]
        ]

        for station in changed:
            conn.execute(
                """
                INSERT INTO meta.station_status_seen (station_id, last_reported)
                VALUES (?, ?)
                ON CONFLICT (station_id) DO UPDATE SET
                    last_reported = excluded.last_reported,
                    seen_at = now()
                """,
                [station["station_id"], station["last_reported"]],
            )
    return changed


def poll_once(
    topic_id: str | None = None,
    stations: list[dict[str, Any]] | None = None,
) -> int:
    """Busca o status atual (ou usa `stations` injetado, para teste), publica
    so' as mudancas e devolve quantas publicou.
    """
    if stations is None:
        stations = fetch_station_status()
    changed = _filter_changed_stations(stations)
    for station in changed:
        messaging.publish_json(station, topic_id)
    return len(changed)
