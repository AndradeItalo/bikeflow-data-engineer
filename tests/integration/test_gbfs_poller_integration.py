"""Teste de integracao do poller GBFS: Pub/Sub real, estacoes injetadas (sem HTTP)."""

from __future__ import annotations

import pytest

from bikeflow.common import messaging
from bikeflow.ingestion.gbfs.poller import poll_once

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("isolated_duckdb")]


def test_poll_once_publishes_changed_stations(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)
    messaging.ensure_subscription(subscription_id, topic_id)
    stations = [
        {"station_id": "a", "last_reported": 100},
        {"station_id": "b", "last_reported": 200},
    ]

    published = poll_once(topic_id, stations=stations)

    assert published == 2
    received = messaging.pull_once(max_messages=10, subscription_id=subscription_id)
    assert sorted(received, key=lambda s: s["station_id"]) == stations


def test_poll_once_skips_unchanged_stations_on_second_call(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)
    messaging.ensure_subscription(subscription_id, topic_id)
    stations = [{"station_id": "a", "last_reported": 100}]

    poll_once(topic_id, stations=stations)
    messaging.pull_once(max_messages=10, subscription_id=subscription_id)  # drena a primeira leva

    published = poll_once(topic_id, stations=stations)

    assert published == 0
