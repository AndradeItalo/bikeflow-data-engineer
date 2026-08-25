"""Configuracao central, lida do ambiente (.env em dev, env vars em producao).

Um unico objeto Settings e' a fonte da verdade. O resto do codigo NUNCA le
os.environ direto - se ler, a configuracao vira invisivel e cada modulo
inventa o proprio default.
"""

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao do BikeFlow.

    Os nomes das variaveis de ambiente sao os MESMOS que o GCP usa
    (STORAGE_EMULATOR_HOST, PUBSUB_EMULATOR_HOST) porque os SDKs do Google
    leem essas variaveis por conta propria, direto do processo - nao a partir
    deste objeto. get_settings() exporta os dois valores de volta para
    os.environ depois de ler o .env, senao um .env nao carregado no shell
    (comum em CI e em execucao direta de script) faz o SDK tentar falar com o
    GCP real em vez do emulador.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Identidade -------------------------------------------------------
    gcp_project_id: str = Field(default="bikeflow-local", alias="GCP_PROJECT_ID")

    # --- Emuladores -------------------------------------------------------
    # Quando estas duas sao None, o mesmo codigo fala com o GCP de verdade.
    storage_emulator_host: str | None = Field(default=None, alias="STORAGE_EMULATOR_HOST")
    pubsub_emulator_host: str | None = Field(default=None, alias="PUBSUB_EMULATOR_HOST")

    # --- Data lake --------------------------------------------------------
    bucket: str = Field(default="bikeflow-lake", alias="BIKEFLOW_BUCKET")

    # --- Pub/Sub ----------------------------------------------------------
    topic: str = Field(default="station-status", alias="BIKEFLOW_TOPIC")
    subscription: str = Field(default="station-status-sub", alias="BIKEFLOW_SUBSCRIPTION")
    dlq_topic: str = Field(default="station-status-dlq", alias="BIKEFLOW_DLQ_TOPIC")

    # --- Warehouse --------------------------------------------------------
    duckdb_path: str = Field(default="data/bikeflow.duckdb", alias="BIKEFLOW_DUCKDB_PATH")

    @property
    def using_storage_emulator(self) -> bool:
        """True quando o Cloud Storage aponta para o emulador local."""
        return self.storage_emulator_host is not None

    @property
    def using_pubsub_emulator(self) -> bool:
        """True quando o Pub/Sub aponta para o emulador local."""
        return self.pubsub_emulator_host is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings em cache.

    lru_cache para o .env ser lido uma vez so' por processo. Nos testes,
    chame get_settings.cache_clear() depois de mexer no ambiente.
    """
    settings = Settings()
    if settings.storage_emulator_host:
        os.environ.setdefault("STORAGE_EMULATOR_HOST", settings.storage_emulator_host)
    if settings.pubsub_emulator_host:
        os.environ.setdefault("PUBSUB_EMULATOR_HOST", settings.pubsub_emulator_host)
    return settings
