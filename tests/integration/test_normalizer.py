"""Teste de integracao da normalizacao zip -> Parquet -> bronze.trips."""

from __future__ import annotations

import io
import zipfile

import pytest

from bikeflow.common import manifest, storage, warehouse
from bikeflow.ingestion.trips.normalizer import load_trip_file_to_bronze

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("isolated_duckdb")]

_CSV_CONTENT = (
    "ride_id,rideable_type,started_at,ended_at,start_station_name,start_station_id,"
    "end_station_name,end_station_id,start_lat,start_lng,end_lat,end_lng,member_casual\n"
    "R1,classic_bike,2025-02-22 17:40:16.500,2025-02-22 17:47:22.479,Jersey & 3rd,JC074,"
    "Van Vorst Park,JC035,40.7233,-74.0459,40.7184,-74.0477,casual\n"
    "R2,electric_bike,2025-02-21 12:28:13.319,2025-02-21 12:35:44.762,Jersey & 3rd,JC074,"
    "Columbus Drive,JC014,40.7233,-74.0459,40.7183,-74.0389,member\n"
)


def _build_sample_zip() -> bytes:
    """Monta um zip com o CSV real + o lixo __MACOSX que o bucket real tem."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("202502-citibike-tripdata.csv", _CSV_CONTENT)
        archive.writestr("__MACOSX/._202502-citibike-tripdata.csv", b"junk")
    return buffer.getvalue()


def test_load_trip_file_to_bronze(bucket_name):
    storage.ensure_bucket(bucket_name)
    source_key = "202502-citibike-tripdata.zip"
    zip_bytes = _build_sample_zip()
    storage.upload_stream(
        f"landing/trips/{source_key}", io.BytesIO(zip_bytes), bucket_name=bucket_name
    )
    manifest.record_download(
        source_key, "https://example.com/x", "etag-1", len(zip_bytes), "batch-1"
    )

    row_count = load_trip_file_to_bronze(source_key, "batch-1", bucket_name=bucket_name)

    assert row_count == 2
    with warehouse.get_connection() as conn:
        rows = conn.execute(
            "SELECT ride_id, member_casual, _source_file, _batch_id "
            "FROM bronze.trips ORDER BY ride_id"
        ).fetchall()
    assert rows == [
        ("R1", "casual", source_key, "batch-1"),
        ("R2", "member", source_key, "batch-1"),
    ]

    # o arquivo agora conta como "ja' baixado" (status virou 'loaded', nao mais
    # so' 'downloaded') - senao o downloader baixaria de novo a toa.
    assert manifest.already_downloaded(source_key, "etag-1") is True
