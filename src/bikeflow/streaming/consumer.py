"""Consumidor de streaming: Pub/Sub -> bronze.station_status.

Mensagem que falha o processamento NAO recebe ack - e' explicitamente
"nackada" (modify_ack_deadline com 0s) para redelivery imediata. Depois de
max_delivery_attempts (configurado na subscription via
messaging.ensure_subscription), o proprio Pub/Sub redireciona para a DLQ -
testado contra o emulador de verdade, nao e' suposicao.

Detalhe do emulador (nao documentado, achado testando): a mensagem so' e'
efetivamente movida para a DLQ como efeito colateral da PROXIMA tentativa de
pull na subscription de origem depois de esgotar max_delivery_attempts - nao
e' um processo em background. Na pratica isso nao muda nada aqui (o poller
roda de novo a cada ciclo de qualquer forma), mas explica um atraso de ate'
1 ciclo entre "esgotou as tentativas" e "apareceu na DLQ".
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from bikeflow.common import messaging, warehouse

logger = logging.getLogger(__name__)

_CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS bronze"
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bronze.station_status (
    station_id            VARCHAR,
    num_bikes_available   BIGINT,
    num_bikes_disabled    BIGINT,
    num_docks_available   BIGINT,
    num_docks_disabled    BIGINT,
    is_installed          INTEGER,
    is_renting            INTEGER,
    is_returning          INTEGER,
    last_reported         BIGINT,
    num_ebikes_available  BIGINT,
    _ingested_at          TIMESTAMP NOT NULL DEFAULT now(),
    _batch_id             VARCHAR
)
"""

_REQUIRED_FIELDS = ("station_id", "last_reported")


def _load_station_status(conn: Any, station: dict[str, Any], batch_id: str) -> None:
    conn.execute(
        """
        INSERT INTO bronze.station_status (
            station_id, num_bikes_available, num_bikes_disabled,
            num_docks_available, num_docks_disabled, is_installed,
            is_renting, is_returning, last_reported, num_ebikes_available,
            _batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            station["station_id"],
            station.get("num_bikes_available"),
            station.get("num_bikes_disabled"),
            station.get("num_docks_available"),
            station.get("num_docks_disabled"),
            station.get("is_installed"),
            station.get("is_renting"),
            station.get("is_returning"),
            station["last_reported"],
            station.get("num_ebikes_available"),
            batch_id,
        ],
    )


def consume_once(
    max_messages: int = 10,
    subscription_id: str | None = None,
    batch_id: str | None = None,
    timeout: float = 10,
) -> int:
    """Puxa ate' N mensagens e carrega em bronze.station_status.

    So' da' ack em mensagens processadas com sucesso. As que falham (JSON
    invalido, campo obrigatorio faltando, erro de carga) sao nackadas
    imediatamente, para redelivery/DLQ - nunca derrubam o consumidor nem as
    outras mensagens do lote.

    Sem mensagem disponivel, bloqueia ate' `timeout` (mesmo comportamento de
    messaging.pull_once).

    Devolve quantas mensagens foram processadas com sucesso.
    """
    batch_id = batch_id or uuid.uuid4().hex
    subscriber = messaging.get_subscriber()
    path = messaging.subscription_path(subscription_id)
    response = subscriber.pull(subscription=path, max_messages=max_messages, timeout=timeout)

    processed = 0
    ack_ids = []
    nack_ids = []
    with warehouse.get_connection() as conn:
        conn.execute(_CREATE_SCHEMA)
        conn.execute(_CREATE_TABLE)
        for received in response.received_messages:
            try:
                station = json.loads(received.message.data.decode("utf-8"))
                if not all(field in station for field in _REQUIRED_FIELDS):
                    raise ValueError(f"campos obrigatorios faltando: {station}")
                _load_station_status(conn, station, batch_id)
            except Exception:
                logger.exception("falha processando mensagem, nack para redelivery/DLQ")
                nack_ids.append(received.ack_id)
                continue
            ack_ids.append(received.ack_id)
            processed += 1

    if ack_ids:
        subscriber.acknowledge(subscription=path, ack_ids=ack_ids)
    if nack_ids:
        subscriber.modify_ack_deadline(subscription=path, ack_ids=nack_ids, ack_deadline_seconds=0)

    return processed
