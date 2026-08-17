"""Acesso a object storage.

ESTE MODULO E' O CORACAO DA ESTRATEGIA LOCAL-FIRST.

Repare no que ele NAO tem: nenhum `if emulador: ... else: ...`. O SDK oficial
do Google ja' resolve isso sozinho. Lendo o codigo de
google/cloud/storage/client.py (linhas ~191-265) da' para ver que quando
STORAGE_EMULATOR_HOST esta' setada ele:
  1. usa esse valor como api_endpoint, e
  2. injeta AnonymousCredentials() automaticamente.

Ou seja: `storage.Client(project=...)` fala com o fake-gcs-server em dev e com
o Cloud Storage real em producao, sem uma linha de codigo diferente.

>>> IMPLEMENTE OS CORPOS DAS FUNCOES ABAIXO (Etapa 0.3). <<<
"""

from __future__ import annotations

from typing import BinaryIO

from google.cloud import storage

# Voce vai precisar deste import ao implementar (deixei fora para o ruff nao
# reclamar de import nao usado enquanto os corpos estao vazios):
#
#     from bikeflow.common.config import get_settings


def get_client() -> storage.Client:
    """Devolve um client de Cloud Storage.

    DICA: e' literalmente uma linha. Passe `project=` explicitamente vindo do
    get_settings() - o SDK so' descobre o projeto sozinho se as variaveis
    GOOGLE_CLOUD_PROJECT/GCLOUD_PROJECT existirem, e nos usamos GCP_PROJECT_ID.

    Nao passe credenciais nem endpoint. Deixe o SDK resolver.
    """
    raise NotImplementedError


def ensure_bucket(name: str | None = None) -> storage.Bucket:
    """Garante que o bucket existe e devolve ele. Idempotente.

    Chamar duas vezes NAO pode dar erro - esta funcao roda a cada bootstrap.

    DICA: `client.lookup_bucket(name)` devolve None se nao existir (nao levanta
    excecao), o que deixa o codigo mais limpo que um try/except em volta de
    `get_bucket`. Se vier None, crie com `client.create_bucket(name)`.

    Args:
        name: nome do bucket. None usa o padrao de get_settings().bucket.
    """
    raise NotImplementedError


def upload_stream(
    blob_name: str,
    fileobj: BinaryIO,
    content_type: str = "application/octet-stream",
    bucket_name: str | None = None,
) -> str:
    """Sobe um arquivo a partir de um objeto de arquivo, SEM ler tudo na RAM.

    Por que streaming e nao `blob.upload_from_string(response.content)`:
    os zips mensais do Citi Bike passam de 1 GB. Ler inteiro na memoria e' a
    falha A6 que a gente encontrou no plano original.

    DICA: `blob.upload_from_file(fileobj, content_type=...)` ja' faz upload em
    chunks por baixo dos panos.

    Returns:
        O caminho gs:// completo do objeto criado.
    """
    raise NotImplementedError


def blob_exists(blob_name: str, bucket_name: str | None = None) -> bool:
    """Diz se o objeto existe.

    Vai ser usado na Fase 1 para pular downloads ja' feitos (idempotencia).
    """
    raise NotImplementedError


def download_bytes(blob_name: str, bucket_name: str | None = None) -> bytes:
    """Baixa o objeto inteiro como bytes.

    So' para arquivos pequenos (JSON do GBFS, fixtures de teste). Para os zips
    grandes, use download em streaming - que a gente escreve na Fase 1.
    """
    raise NotImplementedError
