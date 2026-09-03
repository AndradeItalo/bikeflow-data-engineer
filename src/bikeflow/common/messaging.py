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
    dead_letter_topic_id: str | None = None,
    max_delivery_attempts: int = 5,
) -> str:
    """Cria a subscription se nao existir. Idempotente. Devolve o caminho.

    dead_letter_topic_id: se passado, mensagem que falhar o processamento
    (nao receber ack) N vezes e' redirecionada pelo proprio Pub/Sub para esse
    topico - testado contra o emulador de verdade, ele implementa isso.
    max_delivery_attempts minimo e' 5 no Pub/Sub real (o emulador nao valida,
    mas usar <5 aqui quebraria na migracao para GCP).

    dead_letter_policy nao e' um argumento "achatado" deste metodo - so' da'
    pra passar via `request=` completo, diferente de name/topic.
    """
    subscriber = get_subscriber()
    sub_path = subscription_path(subscription_id)
    tp_path = topic_path(topic_id)

    request: dict[str, Any] = {"name": sub_path, "topic": tp_path}
    if dead_letter_topic_id:
        request["dead_letter_policy"] = {
            "dead_letter_topic": topic_path(dead_letter_topic_id),
            "max_delivery_attempts": max_delivery_attempts,
        }

    with contextlib.suppress(exceptions.AlreadyExists):
        subscriber.create_subscription(request=request)
    return sub_path


def ensure_dlq(max_delivery_attempts: int = 5) -> tuple[str, str]:
    """Liga a DLQ de verdade na subscription principal + cria a subscription da propria DLQ.

    Achado real (Fase 5.5): desde a Fase 3 so' o teste de integracao ligava
    dead_letter_topic_id de verdade - o bootstrap de producao (seed-bronze)
    chamava ensure_subscription() sem isso, entao a subscription real do
    projeto nunca teve DLQ nenhuma. Mensagem invalida ficaria sendo
    redelivered pra sempre, nunca aparecendo em lugar nenhum pra alertar.

    Idempotente feito o resto do modulo: seguro chamar de novo (create_subscription
    ja' existente e' suprimido). Como o emulador nao persiste nada entre
    reinicios (module docstring), nao ha' risco de "subscription antiga sem
    DLQ" sobreviver a um 'make up' novo.
    """
    settings = get_settings()
    ensure_topic(settings.dlq_topic)
    main_sub = ensure_subscription(
        dead_letter_topic_id=settings.dlq_topic, max_delivery_attempts=max_delivery_attempts
    )
    dlq_sub = ensure_subscription(settings.dlq_subscription, settings.dlq_topic)
    return main_sub, dlq_sub


def peek_dlq(max_messages: int = 10, timeout: float = 5) -> list[dict[str, Any]]:
    """Olha o que esta' na DLQ sem consumir - nack tudo de volta logo depois do pull.

    Nem o emulador nem o Pub/Sub real expoe uma contagem direta de fila;
    pull e' a unica forma de "ver" o que esta' la'. Nackar (em vez de ack)
    evita que checar a DLQ destrua a propria evidencia do problema antes de
    alguem investigar - usado pelo alerta de "DLQ > 0" (Fase 5.5).
    """
    subscriber = get_subscriber()
    path = subscription_path(get_settings().dlq_subscription)
    response = subscriber.pull(subscription=path, max_messages=max_messages, timeout=timeout)

    payloads = [json.loads(r.message.data.decode("utf-8")) for r in response.received_messages]
    ack_ids = [r.ack_id for r in response.received_messages]
    if ack_ids:
        subscriber.modify_ack_deadline(subscription=path, ack_ids=ack_ids, ack_deadline_seconds=0)
    return payloads


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
