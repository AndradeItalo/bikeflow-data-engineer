"""Cliente de Cloud Storage.

O SDK escolhe sozinho entre o emulador (STORAGE_EMULATOR_HOST) e o GCS real -
nao ha' branch de ambiente neste modulo.
"""

from __future__ import annotations

from typing import BinaryIO

from google.cloud import storage

from bikeflow.common.config import get_settings


def get_client() -> storage.Client:
    """Client de Cloud Storage para o projeto configurado."""
    settings = get_settings()
    return storage.Client(project=settings.gcp_project_id)


def ensure_bucket(name: str | None = None) -> storage.Bucket:
    """Garante que o bucket existe e devolve ele. Idempotente."""
    client = get_client()
    settings = get_settings()
    bucket_name = name or settings.bucket
    bucket = client.lookup_bucket(bucket_name)
    if bucket is None:
        bucket = client.create_bucket(bucket_name)
    return bucket


def upload_stream(
    blob_name: str,
    fileobj: BinaryIO,
    content_type: str = "application/octet-stream",
    bucket_name: str | None = None,
) -> str:
    """Sobe um arquivo via streaming (sem carregar tudo em memoria).

    Returns:
        O caminho gs:// completo do objeto criado.
    """
    settings = get_settings()
    bucket = get_client().bucket(bucket_name or settings.bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_file(fileobj, content_type=content_type)
    return f"gs://{bucket.name}/{blob_name}"


def blob_exists(blob_name: str, bucket_name: str | None = None) -> bool:
    """Diz se o objeto existe no bucket."""
    settings = get_settings()
    bucket = get_client().bucket(bucket_name or settings.bucket)
    return bucket.blob(blob_name).exists()


def download_bytes(blob_name: str, bucket_name: str | None = None) -> bytes:
    """Baixa o objeto inteiro como bytes. So' para arquivos pequenos."""
    settings = get_settings()
    bucket = get_client().bucket(bucket_name or settings.bucket)
    return bucket.blob(blob_name).download_as_bytes()


def download_to_file(blob_name: str, destination: str, bucket_name: str | None = None) -> None:
    """Baixa o objeto para um arquivo local, sem carregar tudo em memoria.

    Para os zips de viagem, que passam de 300MB - download_bytes() estouraria RAM.
    """
    settings = get_settings()
    bucket = get_client().bucket(bucket_name or settings.bucket)
    bucket.blob(blob_name).download_to_filename(destination)
