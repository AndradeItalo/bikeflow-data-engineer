"""Testes de integracao para messaging.py contra o Pub/Sub emulator."""

from __future__ import annotations

import pytest

from bikeflow.common import messaging

pytestmark = pytest.mark.integration


def test_ensure_topic_is_idempotent(topic_id):
    first = messaging.ensure_topic(topic_id)
    second = messaging.ensure_topic(topic_id)
    assert first == second


def test_ensure_subscription_is_idempotent(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)

    first = messaging.ensure_subscription(subscription_id, topic_id)
    second = messaging.ensure_subscription(subscription_id, topic_id)

    assert first == second


def test_publish_and_pull_roundtrip(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)
    messaging.ensure_subscription(subscription_id, topic_id)
    payload = {"station_id": "123", "bikes_available": 4}

    messaging.publish_json(payload, topic_id)
    received = messaging.pull_once(max_messages=1, subscription_id=subscription_id)

    assert received == [payload]


def test_pull_once_returns_empty_when_no_messages(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)
    messaging.ensure_subscription(subscription_id, topic_id)

    assert messaging.pull_once(max_messages=1, subscription_id=subscription_id, timeout=1) == []
