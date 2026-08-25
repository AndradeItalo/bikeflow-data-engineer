"""Cliente de Pub/Sub.

O SDK escolhe sozinho entre o emulador (PUBSUB_EMULATOR_HOST, sem scheme) e o
Pub/Sub real. O emulador nao persiste nada entre reinicios - topico e
subscription sao recriados a cada 'make up', por isso ensure_topic e
ensure_subscription sao idempotentes.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from google.api_core import exceptions
from google.cloud import pubsub_v1

from bikeflow.common.config import get_settings


def get_publisher() -> pubsub_v1.PublisherClient:
    """Publisher client do Pub/Sub.

    get_settings() roda antes de instanciar o client: e' ela quem exporta
    PUBSUB_EMULATOR_HOST para o processo, e o client decide o endpoint no
    momento em que e' criado - depois disso, mudar a env var nao tem efeito.
    """
    get_settings()
    return pubsub_v1.PublisherClient()


def get_subscriber() -> pubsub_v1.SubscriberClient:
    """Subscriber client do Pub/Sub. Mesmo motivo de get_publisher()."""
    get_settings()
    return pubsub_v1.SubscriberClient()


def topic_path(topic_id: str | None = None) -> str:
    """Caminho completo do topico: projects/<projeto>/topics/<topico>."""
    settings = get_settings()
    return pubsub_v1.PublisherClient.topic_path(settings.gcp_project_id, topic_id or settings.topic)


def subscription_path(subscription_id: str | None = None) -> str:
    """Caminho completo da subscription: projects/<projeto>/subscriptions/<sub>."""
    settings = get_settings()
    return pubsub_v1.SubscriberClient.subscription_path(
        settings.gcp_project_id, subscription_id or settings.subscription
    )


def ensure_topic(topic_id: str | None = None) -> str:
    """Cria o topico se nao existir. Idempotente. Devolve o caminho completo."""
    publisher = get_publisher()
    path = topic_path(topic_id)
    with contextlib.suppress(exceptions.AlreadyExists):
        publisher.create_topic(name=path)
    return path


def ensure_subscription(
    subscription_id: str | None = None,
    topic_id: str | None = None,
) -> str:
    """Cria a subscription se nao existir. Idempotente. Devolve o caminho.

    Dead-letter policy fica para a Fase 3 - aqui so' o caminho feliz.
    """
    subscriber = get_subscriber()
    sub_path = subscription_path(subscription_id)
    tp_path = topic_path(topic_id)
    with contextlib.suppress(exceptions.AlreadyExists):
        subscriber.create_subscription(name=sub_path, topic=tp_path)
    return sub_path


def publish_json(payload: dict[str, Any], topic_id: str | None = None) -> str:
    """Publica um dict como JSON. Bloqueia ate' confirmar o envio. Devolve o message_id."""
    publisher = get_publisher()
    path = topic_path(topic_id)
    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(path, data)
    return future.result()


def pull_once(
    max_messages: int = 10,
    subscription_id: str | None = None,
    timeout: float = 10,
) -> list[dict[str, Any]]:
    """Puxa ate' N mensagens pendentes e da' ack. Devolve os payloads decodificados.

    Pull sincrono, usado em teste e checkpoint - o consumidor real (Fase 3)
    usa streaming pull. Sem mensagem disponivel, bloqueia ate' `timeout`.
    """
    subscriber = get_subscriber()
    path = subscription_path(subscription_id)
    response = subscriber.pull(subscription=path, max_messages=max_messages, timeout=timeout)

    payloads = []
    ack_ids = []
    for received in response.received_messages:
        payloads.append(json.loads(received.message.data.decode("utf-8")))
        ack_ids.append(received.ack_id)

    if ack_ids:
        subscriber.acknowledge(subscription=path, ack_ids=ack_ids)

    return payloads
