"""Fixtures compartilhadas entre tests/unit e tests/integration."""

from __future__ import annotations

import pytest

from bikeflow.common.config import get_settings


@pytest.fixture
def isolated_duckdb(tmp_path, monkeypatch):
    """Aponta BIKEFLOW_DUCKDB_PATH para um arquivo temporario, isolado por teste."""
    monkeypatch.setenv("BIKEFLOW_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
