"""Download em streaming de um arquivo de viagens da Citi Bike para a landing.

Idempotente por ETag (ver bikeflow.common.manifest): se o mesmo source_key
com o mesmo etag ja' foi baixado com sucesso, o download e' pulado.
"""

from __future__ import annotations

import uuid
from typing import BinaryIO, Literal, cast

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from bikeflow.common import manifest, storage
from bikeflow.ingestion.trips.resolver import resolve_trip_file


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _fetch(url: str) -> requests.Response:
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    return response


def download_trip_file(
    year: int,
    month: int,
    group: Literal["nyc", "jc"] = "nyc",
    batch_id: str | None = None,
    bucket_name: str | None = None,
) -> str | None:
    """Baixa o arquivo de viagens de um ano-mes para a landing, se necessario.

    Devolve o caminho gs:// do objeto criado, ou None se pulou (mesmo
    source_key e etag ja' baixados antes).
    """
    batch_id = batch_id or uuid.uuid4().hex
    resolved = resolve_trip_file(year, month, group)

    if manifest.already_downloaded(resolved.key, resolved.etag):
        return None

    response = _fetch(resolved.url)
    response.raw.decode_content = True
    blob_name = f"landing/trips/{resolved.key}"
    path = storage.upload_stream(blob_name, cast(BinaryIO, response.raw), bucket_name=bucket_name)

    manifest.record_download(
        source_key=resolved.key,
        source_url=resolved.url,
        etag=resolved.etag,
        size_bytes=resolved.size,
        batch_id=batch_id,
    )
    return path
