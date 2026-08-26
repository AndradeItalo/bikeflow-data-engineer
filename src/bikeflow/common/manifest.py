"""Idempotencia de ingestao: registra e consulta o que ja' foi baixado.

Chave de idempotencia e' (source_key, etag): se o ETag do S3 nao mudou desde
a ultima vez que baixamos esse arquivo com sucesso, o download e' pulado.
"""

from __future__ import annotations

from bikeflow.common import warehouse


def already_downloaded(source_key: str, etag: str) -> bool:
    """Diz se esse arquivo, nesse etag exato, ja' foi baixado com sucesso.

    status IN ('downloaded', 'loaded'): 'loaded' tambem conta, senao um
    arquivo ja' processado ate' o bronze seria baixado de novo a toa (o
    status muda de 'downloaded' para 'loaded' em mark_loaded()).
    """
    with warehouse.get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM meta.ingestion_manifest
            WHERE source_key = ? AND etag = ? AND status IN ('downloaded', 'loaded')
            """,
            [source_key, etag],
        ).fetchone()
    return row is not None


def record_download(
    source_key: str,
    source_url: str,
    etag: str,
    size_bytes: int,
    batch_id: str,
    status: str = "downloaded",
) -> None:
    """Registra o resultado de um download. Upsert por source_key."""
    with warehouse.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO meta.ingestion_manifest
                (source_key, source_url, etag, size_bytes, status, batch_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_key) DO UPDATE SET
                source_url = excluded.source_url,
                etag = excluded.etag,
                size_bytes = excluded.size_bytes,
                status = excluded.status,
                batch_id = excluded.batch_id,
                ingested_at = now()
            """,
            [source_key, source_url, etag, size_bytes, status, batch_id],
        )


def mark_loaded(source_key: str, row_count: int) -> None:
    """Marca um arquivo ja' baixado como carregado em bronze, com o total de linhas."""
    with warehouse.get_connection() as conn:
        conn.execute(
            "UPDATE meta.ingestion_manifest SET row_count = ?, status = 'loaded' WHERE source_key = ?",
            [row_count, source_key],
        )
