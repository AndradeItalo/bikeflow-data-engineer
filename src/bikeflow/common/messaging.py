"""Acesso ao Pub/Sub.

Mesma ideia do storage.py: SDK oficial, zero codigo condicional. O
google-cloud-pubsub le PUBSUB_EMULATOR_HOST sozinho e usa esse valor como
api_endpoint (ver pubsub_v1/publisher/client.py:133).

ATENCAO ao formato, e' diferente do storage:
    STORAGE_EMULATOR_HOST = "http://localhost:4443"   <- COM scheme
    PUBSUB_EMULATOR_HOST  = "localhost:8085"          <- SEM scheme

LEMBRETE DE DESIGN: o emulador do Pub/Sub nao persiste nada. Topicos e
subscriptions morrem junto com o container. Por isso ensure_topic e
ensure_subscription PRECISAM ser idempotentes - elas rodam a cada 'make up'.
Isso nao e' gambiarra de emulador: e' o mesmo padrao que voce quer em
producao, onde o recurso pode ja' existir criado pelo Terraform.

>>> IMPLEMENTE OS CORPOS DAS FUNCOES ABAIXO (Etapa 0.3). <<<
"""

from __future__ import annotations

from typing import Any

from google.cloud import pubsub_v1

# Voce vai precisar deste import ao implementar (deixei fora para o ruff nao
# reclamar de import nao usado enquanto os corpos estao vazios):
#
#     from bikeflow.common.config import get_settings


def get_publisher() -> pubsub_v1.PublisherClient:
    """Devolve um publisher client. Uma linha, sem argumentos."""
    raise NotImplementedError


def get_subscriber() -> pubsub_v1.SubscriberClient:
    """Devolve um subscriber client. Uma linha, sem argumentos."""
    raise NotImplementedError


def topic_path(topic_id: str | None = None) -> str:
    """Monta o caminho completo do topico.

    O Pub/Sub nao trabalha com nomes curtos: tudo e' o caminho
    'projects/<projeto>/topics/<topico>'. O client tem um helper
    `.topic_path(project, topic)` que monta isso - use ele em vez de f-string,
    para nao errar o formato.
    """
    raise NotImplementedError


def subscription_path(subscription_id: str | None = None) -> str:
    """Idem para subscription: 'projects/<projeto>/subscriptions/<sub>'."""
    raise NotImplementedError


def ensure_topic(topic_id: str | None = None) -> str:
    """Cria o topico se nao existir. Idempotente. Devolve o caminho completo.

    DICA: o Pub/Sub nao tem um "lookup" que devolve None como o storage tem.
    O padrao aqui e' tentar criar e engolir a excecao de ja'-existe:

        from google.api_core import exceptions
        try:
            publisher.create_topic(name=path)
        except exceptions.AlreadyExists:
            pass

    Engula APENAS AlreadyExists. Um `except Exception: pass` aqui esconderia
    erro de rede e de permissao, e voce ia debugar isso por horas.
    """
    raise NotImplementedError


def ensure_subscription(
    subscription_id: str | None = None,
    topic_id: str | None = None,
) -> str:
    """Cria a subscription se nao existir. Idempotente. Devolve o caminho.

    DICA: `subscriber.create_subscription(name=<sub_path>, topic=<topic_path>)`.
    Mesmo tratamento de AlreadyExists.

    (Dead-letter policy fica para a Fase 3 - aqui so' o caminho feliz.)
    """
    raise NotImplementedError


def publish_json(payload: dict[str, Any], topic_id: str | None = None) -> str:
    """Publica um dict como JSON. Devolve o message_id.

    DUAS ARMADILHAS AQUI:

    1. `publisher.publish()` NAO envia na hora - ela devolve um Future e o SDK
       agrupa mensagens em lote. Se o processo terminar antes do flush, a
       mensagem se perde silenciosamente. Chame `.result()` para bloquear ate'
       confirmar (isso e' o que devolve o message_id).

    2. O payload tem que virar bytes: `json.dumps(payload).encode("utf-8")`.
       Passar str da' TypeError.
    """
    raise NotImplementedError


def pull_once(
    max_messages: int = 10,
    subscription_id: str | None = None,
) -> list[dict[str, Any]]:
    """Puxa ate' N mensagens de uma vez e da' ack. Devolve os payloads decodificados.

    Modo pull sincrono, usado em teste e no checkpoint. O consumidor de
    verdade (Fase 3) usa streaming pull, que e' outro padrao.

    DICA: `subscriber.pull(subscription=<path>, max_messages=N)` devolve um
    objeto com `.received_messages`. Cada item tem `.message.data` (bytes) e
    `.ack_id`. Depois de processar, chame
    `subscriber.acknowledge(subscription=<path>, ack_ids=[...])` - sem o ack,
    a mensagem volta para a fila quando o deadline expira.

    Cuidado: se nao houver mensagem, o pull pode ficar bloqueado ate' o
    timeout. Passe `timeout=` na chamada.
    """
    raise NotImplementedError
