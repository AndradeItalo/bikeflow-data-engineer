"""Teste de integracao do consumidor: Pub/Sub real -> bronze.station_status."""

from __future__ import annotations

import pytest

from bikeflow.common import messaging, warehouse
from bikeflow.streaming.consumer import consume_once

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("isolated_duckdb")]


def test_consume_once_loads_valid_messages_and_acks_them(topic_id, subscription_id):
    messaging.ensure_topic(topic_id)
    messaging.ensure_subscription(subscription_id, topic_id)
    messaging.publish_json(
        {"station_id": "a", "last_reported": 100, "num_bikes_available": 3}, topic_id
    )
    messaging.publish_json(
        {"station_id": "b", "last_reported": 200, "num_bikes_available": 0}, topic_id
    )

    processed = consume_once(max_messages=10, subscription_id=subscription_id, batch_id="batch-1")

    assert processed == 2
    with warehouse.get_connection() as conn:
        rows = conn.execute(
            "SELECT station_id, num_bikes_available FROM bronze.station_status ORDER BY station_id"
        ).fetchall()
    assert rows == [("a", 3), ("b", 0)]

    # ja' foram acked - nao sobra nada pra puxar de novo
    assert messaging.pull_once(max_messages=10, subscription_id=subscription_id, timeout=1) == []


def test_consume_once_sends_invalid_message_to_dlq_after_max_attempts(
    topic_id, subscription_id, dlq_topic_id, dlq_subscription_id
):
    messaging.ensure_topic(topic_id)
    messaging.ensure_topic(dlq_topic_id)
    messaging.ensure_subscription(
        subscription_id, topic_id, dead_letter_topic_id=dlq_topic_id, max_delivery_attempts=5
    )
    messaging.ensure_subscription(dlq_subscription_id, dlq_topic_id)
    # falta last_reported (campo obrigatorio) - mensagem invalida de proposito
    messaging.publish_json({"station_id": "broken"}, topic_id)

    for _ in range(5):
        processed = consume_once(
            max_messages=10, subscription_id=subscription_id, batch_id="batch-x", timeout=2
        )
        assert processed == 0

    # o emulador so' move a mensagem para a DLQ como EFEITO COLATERAL da
    # proxima tentativa de pull na subscription de origem depois de esgotar
    # max_delivery_attempts - nao e' um processo em background. Por isso mais
    # uma chamada aqui antes de checar a DLQ (confirmado testando: sem essa
    # chamada extra, a DLQ aparece vazia mesmo com as 5 tentativas certas).
    consume_once(max_messages=10, subscription_id=subscription_id, batch_id="batch-x", timeout=2)

    dlq_messages = messaging.pull_once(
        max_messages=5, subscription_id=dlq_subscription_id, timeout=5
    )
    assert dlq_messages == [{"station_id": "broken"}]

    with warehouse.get_connection() as conn:
        count = conn.execute("SELECT count(*) FROM bronze.station_status").fetchone()
    assert count == (0,)
