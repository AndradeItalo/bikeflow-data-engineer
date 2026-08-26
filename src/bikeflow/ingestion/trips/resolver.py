"""Resolve o nome real de um arquivo de viagens no bucket publico da Citi Bike.

O indice do bucket nao segue um padrao fixo de extensao: arquivos do grupo JC
(Jersey City) alternam entre `.zip` e `.csv.zip` para o mesmo padrao de nome
(ex: JC-202510-citibike-tripdata.zip vs JC-202511-...csv.zip). Por isso a
resolucao e' sempre contra a listagem real do bucket, nunca um nome montado
na mao.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

import requests

TRIPDATA_INDEX_URL = "https://s3.amazonaws.com/tripdata/"

_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


@dataclass(frozen=True)
class BucketEntry:
    key: str
    etag: str
    size: int


@dataclass(frozen=True)
class ResolvedFile:
    key: str
    url: str
    etag: str
    size: int


def list_bucket_entries(index_url: str = TRIPDATA_INDEX_URL) -> list[BucketEntry]:
    """Lista as entradas (chave, etag, tamanho) do bucket publico de viagens."""
    response = requests.get(index_url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    entries = []
    for contents in root.findall("s3:Contents", _S3_NS):
        key = contents.findtext("s3:Key", namespaces=_S3_NS)
        etag = (contents.findtext("s3:ETag", default="", namespaces=_S3_NS) or "").strip('"')
        size = int(contents.findtext("s3:Size", default="0", namespaces=_S3_NS) or "0")
        if key:
            entries.append(BucketEntry(key=key, etag=etag, size=size))
    return entries


def resolve_trip_file(
    year: int,
    month: int,
    group: Literal["nyc", "jc"] = "nyc",
    entries: list[BucketEntry] | None = None,
) -> ResolvedFile:
    """Encontra a entrada do arquivo de viagens de um ano-mes no bucket.

    entries: lista ja' obtida (para teste, sem rede); None busca no bucket
    via list_bucket_entries().

    Levanta FileNotFoundError se nao existir chave compativel - a resolucao
    nunca inventa uma URL, quem chama decide o que fazer com a ausencia.
    """
    if entries is None:
        entries = list_bucket_entries()

    prefix = "JC-" if group == "jc" else ""
    yyyymm = f"{year:04d}{month:02d}"
    pattern = re.compile(rf"^{re.escape(prefix)}{yyyymm}-citibike-tripdata(\.csv)?\.zip$")

    matches = [entry for entry in entries if pattern.match(entry.key)]
    if not matches:
        raise FileNotFoundError(f"nenhum arquivo de viagens para group={group!r} {yyyymm}")
    if len(matches) > 1:
        keys = [entry.key for entry in matches]
        raise ValueError(f"mais de uma chave casou para group={group!r} {yyyymm}: {keys}")

    entry = matches[0]
    return ResolvedFile(
        key=entry.key,
        url=f"{TRIPDATA_INDEX_URL}{entry.key}",
        etag=entry.etag,
        size=entry.size,
    )
