"""Orquestra o pipeline de um mes de viagens: resolve -> download -> bronze.

Uso pontual (seed de CI, teste manual). A Fase 4 (Airflow) formaliza isso como
DAG de verdade, com idempotencia de carga por particao - aqui e' deliberadamente
simples: rodar para o mesmo mes duas vezes duplica linhas em bronze.trips (sem
problema, Bronze nao tem PK por design e Silver dedupe por ride_id).
"""

from __future__ import annotations

import uuid
from typing import Literal

from bikeflow.ingestion.trips.downloader import download_trip_file
from bikeflow.ingestion.trips.normalizer import load_trip_file_to_bronze
from bikeflow.ingestion.trips.resolver import resolve_trip_file


def ingest_month(
    year: int,
    month: int,
    group: Literal["nyc", "jc"] = "nyc",
    batch_id: str | None = None,
    bucket_name: str | None = None,
) -> int:
    """Baixa e carrega um mes de viagens em bronze.trips. Devolve o row_count."""
    batch_id = batch_id or uuid.uuid4().hex
    resolved_key = resolve_trip_file(year, month, group).key
    download_trip_file(year, month, group, batch_id=batch_id, bucket_name=bucket_name)
    return load_trip_file_to_bronze(resolved_key, batch_id, bucket_name=bucket_name)
