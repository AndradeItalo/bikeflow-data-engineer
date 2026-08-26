"""Testes unitarios do resolver de nome de arquivo de viagens. Sem rede real."""

from __future__ import annotations

import pytest
import responses

from bikeflow.ingestion.trips.resolver import (
    TRIPDATA_INDEX_URL,
    BucketEntry,
    list_bucket_entries,
    resolve_trip_file,
)

# Amostra real da listagem do bucket (capturada de https://s3.amazonaws.com/tripdata/):
# NYC e' sempre .zip; JC alterna .zip/.csv.zip para o mesmo padrao de nome.
SAMPLE_ENTRIES = [
    BucketEntry(key="2023-citibike-tripdata.zip", etag="e-legado", size=1),  # fora do escopo
    BucketEntry(key="202401-citibike-tripdata.zip", etag="e-nyc-202401", size=100),
    BucketEntry(key="JC-202401-citibike-tripdata.csv.zip", etag="e-jc-202401", size=50),
    BucketEntry(key="JC-202510-citibike-tripdata.zip", etag="e-jc-202510", size=60),
    BucketEntry(key="index.html", etag="e-index", size=1),  # nao e' dado
]


def test_resolve_trip_file_nyc_plain_zip():
    resolved = resolve_trip_file(2024, 1, "nyc", entries=SAMPLE_ENTRIES)
    assert resolved.key == "202401-citibike-tripdata.zip"
    assert resolved.url == f"{TRIPDATA_INDEX_URL}202401-citibike-tripdata.zip"
    assert resolved.etag == "e-nyc-202401"
    assert resolved.size == 100


def test_resolve_trip_file_jc_csv_zip():
    resolved = resolve_trip_file(2024, 1, "jc", entries=SAMPLE_ENTRIES)
    assert resolved.key == "JC-202401-citibike-tripdata.csv.zip"


def test_resolve_trip_file_jc_plain_zip_variant():
    resolved = resolve_trip_file(2025, 10, "jc", entries=SAMPLE_ENTRIES)
    assert resolved.key == "JC-202510-citibike-tripdata.zip"


def test_resolve_trip_file_ignores_legacy_yearly_file():
    with pytest.raises(FileNotFoundError):
        resolve_trip_file(2023, 1, "nyc", entries=SAMPLE_ENTRIES)


def test_resolve_trip_file_raises_when_missing():
    with pytest.raises(FileNotFoundError):
        resolve_trip_file(2030, 1, "nyc", entries=SAMPLE_ENTRIES)


@responses.activate
def test_list_bucket_entries_parses_index():
    body = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Contents>
            <Key>202401-citibike-tripdata.zip</Key>
            <ETag>&quot;abc123&quot;</ETag>
            <Size>369035302</Size>
        </Contents>
        <Contents>
            <Key>JC-202401-citibike-tripdata.csv.zip</Key>
            <ETag>&quot;def456&quot;</ETag>
            <Size>12345</Size>
        </Contents>
    </ListBucketResult>"""
    responses.add(responses.GET, TRIPDATA_INDEX_URL, body=body, status=200)

    entries = list_bucket_entries()

    assert entries == [
        BucketEntry(key="202401-citibike-tripdata.zip", etag="abc123", size=369035302),
        BucketEntry(key="JC-202401-citibike-tripdata.csv.zip", etag="def456", size=12345),
    ]
