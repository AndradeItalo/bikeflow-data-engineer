"""Fixtures dos testes de integracao. Exigem os emuladores rodando (make up).

Cada fixture gera um nome unico (bucket/topico/subscription) para o teste nao
interferir com outro rodando em paralelo, e limpa o recurso no teardown.
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from google.api_core import exceptions

from bikeflow.common import messaging, storage


@pytest.fixture
def bucket_name() -> str:
    name = f"test-bucket-{uuid.uuid4().hex[:8]}"
    yield name
    bucket = storage.get_client().lookup_bucket(name)
    if bucket is not None:
        bucket.delete(force=True)


@pytest.fixture
def topic_id() -> str:
    name = f"test-topic-{uuid.uuid4().hex[:8]}"
    yield name
    with contextlib.suppress(exceptions.NotFound):
        messaging.get_publisher().delete_topic(topic=messaging.topic_path(name))


@pytest.fixture
def subscription_id() -> str:
    name = f"test-sub-{uuid.uuid4().hex[:8]}"
    yield name
    with contextlib.suppress(exceptions.NotFound):
        messaging.get_subscriber().delete_subscription(
            subscription=messaging.subscription_path(name)
        )
