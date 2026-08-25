"""Testes de integracao para storage.py contra o fake-gcs-server."""

from __future__ import annotations

import io

import pytest

from bikeflow.common import storage

pytestmark = pytest.mark.integration


def test_ensure_bucket_is_idempotent(bucket_name):
    first = storage.ensure_bucket(bucket_name)
    second = storage.ensure_bucket(bucket_name)
    assert first.name == second.name == bucket_name


def test_upload_download_roundtrip(bucket_name):
    storage.ensure_bucket(bucket_name)
    content = b"hello bikeflow"

    path = storage.upload_stream("greeting.txt", io.BytesIO(content), bucket_name=bucket_name)

    assert path == f"gs://{bucket_name}/greeting.txt"
    assert storage.blob_exists("greeting.txt", bucket_name=bucket_name)
    assert storage.download_bytes("greeting.txt", bucket_name=bucket_name) == content


def test_blob_exists_is_false_for_missing_blob(bucket_name):
    storage.ensure_bucket(bucket_name)
    assert storage.blob_exists("nao-existe.txt", bucket_name=bucket_name) is False
