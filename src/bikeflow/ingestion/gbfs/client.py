"""Cliente GBFS: auto-discovery + fetch dos feeds de estacao.

A URL de auto-discovery e' a unica hardcoded - station_status/station_information
sao resolvidas a partir dela, nunca hardcoded direto, porque o host real
(hoje gbfs.lyft.com) ja' mudou uma vez sem aviso (falha A4 do PLAN.md).

station_id vem em dois formatos misturados no mesmo feed (UUID em algumas
estacoes, numero legado longo em outras) - tratado sempre como string opaca,
nunca convertido pra numero. Nao e' o join key com viagens: isso e'
short_name (ver ADR-0004), que vem so' em station_information.
"""

from __future__ import annotations

from typing import Any

import requests

GBFS_DISCOVERY_URL = "https://gbfs.citibikenyc.com/gbfs/gbfs.json"


def discover_feed_url(feed_name: str, language: str = "en") -> str:
    """Resolve a URL real de um feed GBFS (ex: 'station_status') via auto-discovery."""
    response = requests.get(GBFS_DISCOVERY_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    feeds = data["data"][language]["feeds"]
    matches = [feed["url"] for feed in feeds if feed["name"] == feed_name]
    if not matches:
        raise FileNotFoundError(f"feed {feed_name!r} nao encontrado no auto-discovery")
    return matches[0]


def fetch_station_status() -> list[dict[str, Any]]:
    """Baixa station_status.json (via auto-discovery) e devolve a lista de estacoes."""
    url = discover_feed_url("station_status")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()["data"]["stations"]


def fetch_station_information() -> list[dict[str, Any]]:
    """Baixa station_information.json (via auto-discovery) e devolve a lista de estacoes."""
    url = discover_feed_url("station_information")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()["data"]["stations"]
