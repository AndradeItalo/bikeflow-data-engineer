"""Testes unitarios do manifest de idempotencia. So' toca um DuckDB temporario."""

from __future__ import annotations

import pytest

from bikeflow.common import manifest

pytestmark = pytest.mark.usefixtures("isolated_duckdb")

KEY = "202401-citibike-tripdata.zip"
URL = "https://s3.amazonaws.com/tripdata/202401-citibike-tripdata.zip"


def test_already_downloaded_is_false_before_any_record():
    assert manifest.already_downloaded(KEY, "etag-1") is False


def test_record_download_marks_as_downloaded():
    manifest.record_download(KEY, URL, "etag-1", 123, "batch-1")

    assert manifest.already_downloaded(KEY, "etag-1") is True


def test_already_downloaded_is_false_when_etag_changed():
    manifest.record_download(KEY, URL, "etag-old", 123, "batch-1")

    assert manifest.already_downloaded(KEY, "etag-new") is False


def test_record_download_upserts_same_key():
    manifest.record_download(KEY, URL, "etag-old", 100, "batch-1")
    manifest.record_download(KEY, URL, "etag-new", 200, "batch-2")

    assert manifest.already_downloaded(KEY, "etag-old") is False
    assert manifest.already_downloaded(KEY, "etag-new") is True
