"""Teste de integracao do download de viagens.

HTTP mockado para o bucket publico da Citi Bike (nao faz sentido baixar um
arquivo real de +300MB num teste), mas storage de verdade contra o
fake-gcs-server - e' a landing que queremos provar que funciona.

responses.activate() intercepta TODA chamada via requests no processo, nao
so' a URL que a gente mocka - inclusive as do proprio google-cloud-storage
para o emulador. Sem add_passthru(), essas chamadas ficam sem mock e a lib
entra em retry/backoff tentando de novo, "travando" o teste por minutos em
vez de falhar rapido. add_passthru() libera o trafego real para o emulador,
mockando so' a URL da Citi Bike.
"""

from __future__ import annotations

import pytest
import responses

from bikeflow.common import storage
from bikeflow.common.config import get_settings
from bikeflow.ingestion.trips.downloader import download_trip_file
from bikeflow.ingestion.trips.resolver import TRIPDATA_INDEX_URL

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("isolated_duckdb")]

_FILE_URL = f"{TRIPDATA_INDEX_URL}202401-citibike-tripdata.zip"
_INDEX_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Contents>
        <Key>202401-citibike-tripdata.zip</Key>
        <ETag>&quot;abc123&quot;</ETag>
        <Size>17</Size>
    </Contents>
</ListBucketResult>"""


def _allow_storage_emulator_passthru() -> None:
    emulator_host = get_settings().storage_emulator_host
    if emulator_host:
        responses.add_passthru(emulator_host)


@responses.activate
def test_download_trip_file_uploads_to_landing(bucket_name):
    _allow_storage_emulator_passthru()
    storage.ensure_bucket(bucket_name)
    responses.add(responses.GET, TRIPDATA_INDEX_URL, body=_INDEX_BODY, status=200)
    responses.add(responses.GET, _FILE_URL, body=b"fake zip content", status=200)

    path = download_trip_file(2024, 1, "nyc", batch_id="test-batch", bucket_name=bucket_name)

    assert path == f"gs://{bucket_name}/landing/trips/202401-citibike-tripdata.zip"
    downloaded = storage.download_bytes(
        "landing/trips/202401-citibike-tripdata.zip", bucket_name=bucket_name
    )
    assert downloaded == b"fake zip content"


@responses.activate
def test_download_trip_file_skips_when_already_downloaded(bucket_name):
    _allow_storage_emulator_passthru()
    storage.ensure_bucket(bucket_name)
    responses.add(responses.GET, TRIPDATA_INDEX_URL, body=_INDEX_BODY, status=200)
    responses.add(responses.GET, _FILE_URL, body=b"fake zip content", status=200)

    first = download_trip_file(2024, 1, "nyc", batch_id="batch-1", bucket_name=bucket_name)
    second = download_trip_file(2024, 1, "nyc", batch_id="batch-2", bucket_name=bucket_name)

    assert first is not None
    assert second is None
