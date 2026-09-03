"""Conexao com o warehouse local (DuckDB).

DuckDB e' embarcado: nao ha' client/servidor, o "banco" e' um arquivo no
disco. Abrir/fechar essa conexao e' barato, entao cada chamador pega a sua e
fecha depois de usar - mesmo padrao de client "fresco por chamada" de
storage.py/messaging.py.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from bikeflow.common.config import get_settings

_CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS meta"

_CREATE_MANIFEST_TABLE = """
CREATE TABLE IF NOT EXISTS meta.ingestion_manifest (
    source_key   VARCHAR PRIMARY KEY,
    source_url   VARCHAR NOT NULL,
    etag         VARCHAR NOT NULL,
    size_bytes   BIGINT NOT NULL,
    row_count    BIGINT,
    status       VARCHAR NOT NULL,
    batch_id     VARCHAR NOT NULL,
    ingested_at  TIMESTAMP NOT NULL DEFAULT now()
)
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    """Conexao com o warehouse local. Garante o schema de manifest antes de devolver.

    Ao contrario de ensure_bucket()/ensure_topic() (chamadas a parte), aqui a
    garantia de schema entra direto na conexao: rodar DDL local e' uma
    operacao de arquivo, nao uma chamada de rede - o custo de repetir a cada
    conexao e' desprezivel.
    """
    settings = get_settings()
    Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(settings.duckdb_path)
    # Sem isso, now() devolve o horario LOCAL do sistema (fuso do ambiente),
    # nao UTC - quebra toda coluna DEFAULT now() do projeto (_ingested_at,
    # ingested_at, etc). So' apareceu rodando dbt source freshness (Fase 5.2)
    # - nenhuma checagem anterior comparava contra um limite de tempo curto
    # o bastante pra expor a diferenca de fuso.
    conn.execute("SET TimeZone='UTC'")
    conn.execute(_CREATE_SCHEMA)
    conn.execute(_CREATE_MANIFEST_TABLE)
    return conn
