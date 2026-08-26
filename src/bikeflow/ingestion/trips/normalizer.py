"""Normaliza um zip de viagens (landing) para Parquet e carrega em bronze.trips.

O zip real da Citi Bike, alem do CSV, costuma trazer lixo de metadado do Mac
(__MACOSX/._<nome>.csv) - so' o membro .csv que nao comeca com __MACOSX/ e'
processado. Schema confirmado direto num arquivo real (JC-202502):
ride_id, rideable_type, started_at, ended_at, start_station_name,
start_station_id, end_station_name, end_station_id, start_lat, start_lng,
end_lat, end_lng, member_casual - zero regra de negocio aqui, e' 1:1 com a
fonte, so' com colunas de linhagem a mais.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq

from bikeflow.common import manifest, storage, warehouse

_READ_OPTIONS = pa_csv.ReadOptions(block_size=8 * 1024 * 1024)
_CONVERT_OPTIONS = pa_csv.ConvertOptions(
    column_types={
        "ride_id": pa.string(),
        "rideable_type": pa.string(),
        "started_at": pa.timestamp("us"),
        "ended_at": pa.timestamp("us"),
        "start_station_name": pa.string(),
        "start_station_id": pa.string(),
        "end_station_name": pa.string(),
        "end_station_id": pa.string(),
        "start_lat": pa.float64(),
        "start_lng": pa.float64(),
        "end_lat": pa.float64(),
        "end_lng": pa.float64(),
        "member_casual": pa.string(),
    }
)

_CREATE_BRONZE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS bronze"
_CREATE_TRIPS_TABLE = """
CREATE TABLE IF NOT EXISTS bronze.trips (
    ride_id             VARCHAR,
    rideable_type       VARCHAR,
    started_at          TIMESTAMP,
    ended_at            TIMESTAMP,
    start_station_name  VARCHAR,
    start_station_id    VARCHAR,
    end_station_name    VARCHAR,
    end_station_id      VARCHAR,
    start_lat           DOUBLE,
    start_lng           DOUBLE,
    end_lat             DOUBLE,
    end_lng             DOUBLE,
    member_casual       VARCHAR,
    _source_file        VARCHAR NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT now(),
    _batch_id           VARCHAR NOT NULL
)
"""


def _extract_csv_member(zip_path: Path, extract_dir: Path) -> Path:
    """Extrai o unico membro .csv real do zip, ignorando o lixo do __MACOSX."""
    with zipfile.ZipFile(zip_path) as archive:
        csv_members = [
            name
            for name in archive.namelist()
            if name.endswith(".csv") and not name.startswith("__MACOSX/")
        ]
        if len(csv_members) != 1:
            raise ValueError(f"esperava 1 CSV no zip, achei {csv_members}")
        extracted = archive.extract(csv_members[0], path=extract_dir)
    return Path(extracted)


def _csv_to_parquet(csv_path: Path, parquet_path: Path, source_file: str, batch_id: str) -> int:
    """Converte o CSV para Parquet em chunks, com colunas de linhagem. Devolve o row_count."""
    reader = pa_csv.open_csv(csv_path, read_options=_READ_OPTIONS, convert_options=_CONVERT_OPTIONS)
    row_count = 0
    writer: pq.ParquetWriter | None = None
    try:
        for batch in reader:
            table = pa.Table.from_batches([batch])
            table = table.append_column(
                "_source_file", pa.array([source_file] * table.num_rows, type=pa.string())
            )
            table = table.append_column(
                "_batch_id", pa.array([batch_id] * table.num_rows, type=pa.string())
            )
            if writer is None:
                writer = pq.ParquetWriter(parquet_path, table.schema)
            writer.write_table(table)
            row_count += table.num_rows
    finally:
        if writer is not None:
            writer.close()
    return row_count


def load_trip_file_to_bronze(
    source_key: str,
    batch_id: str,
    bucket_name: str | None = None,
) -> int:
    """Baixa o zip da landing, normaliza pra Parquet e carrega em bronze.trips.

    Devolve o numero de linhas carregadas. Assume que source_key ja' foi
    baixado antes (bikeflow.ingestion.trips.downloader) e tem uma linha em
    meta.ingestion_manifest.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "trip.zip"
        parquet_path = tmp_dir / "trip.parquet"

        storage.download_to_file(
            f"landing/trips/{source_key}", str(zip_path), bucket_name=bucket_name
        )
        csv_path = _extract_csv_member(zip_path, tmp_dir)
        row_count = _csv_to_parquet(csv_path, parquet_path, source_key, batch_id)

        with warehouse.get_connection() as conn:
            conn.execute(_CREATE_BRONZE_SCHEMA)
            conn.execute(_CREATE_TRIPS_TABLE)
            conn.execute(
                "INSERT INTO bronze.trips BY NAME SELECT * FROM read_parquet(?)",
                [str(parquet_path)],
            )

    manifest.mark_loaded(source_key, row_count)
    return row_count
