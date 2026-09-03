.DEFAULT_GOAL := help
.PHONY: help venv install install-dbt up down logs lint fmt test test-all seed-bronze dbt-debug dbt-deps dbt-build airflow-up airflow-logs clean

# O diretorio de binarios do venv muda de nome entre Windows e Unix:
#   Windows -> .venv/Scripts    Linux/macOS -> .venv/bin
# Detectar aqui faz 'make lint' funcionar igual na sua maquina e no CI, sem
# ninguem precisar lembrar de ativar o venv antes.
VENV := .venv
ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
else
	BIN := $(VENV)/bin
endif
PY := $(BIN)/python
DBT_DIR := transform/dbt_bikeflow

help:  ## Mostra os comandos disponiveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv:  ## Cria o virtualenv (roda uma vez)
	python -m venv $(VENV)

install: venv  ## Cria o venv e instala o pacote em modo editavel + deps de dev
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

install-dbt:  ## Instala o extra dbt (separado - so' quem mexe em silver/gold precisa)
	$(PY) -m pip install -e ".[dbt]"

up:  ## Sobe os emuladores (fake-gcs + pub/sub) e espera ficarem saudaveis
	docker compose up -d --wait
	@echo "Emuladores no ar."

down:  ## Derruba TUDO (emuladores + Airflow, se estiver de pe') e apaga os volumes
	# --profile airflow aqui e' de proposito, mesmo 'up' nao usando: sem isso,
	# 'docker compose down' (sem --profile) ignora containers de profile nao
	# ativado e eles ficam rodando orfaos em segundo plano - achado testando,
	# nao suposicao. down = tudo limpo sempre; so' 'up' fica dividido por
	# velocidade (up rapido vs airflow-up pesado).
	docker compose --profile airflow down -v

logs:  ## Acompanha os logs dos emuladores
	docker compose logs -f

lint:  ## Roda ruff (lint + formato) e mypy
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/mypy

fmt:  ## Formata e corrige o que for auto-corrigivel
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

test:  ## Testes unitarios (nao precisa de emulador)
	$(BIN)/pytest -m "not integration"

test-all:  ## Todos os testes, inclusive integracao (rode 'make up' antes)
	$(BIN)/pytest

seed-bronze:  ## Ingere 1 mes real pequeno (JC) + snapshot e 1 ciclo de poll/consume do GBFS em bronze
	# bucket precisa existir antes do 1o upload - so' "funcionava" sem isso
	# localmente porque o fake-gcs persiste em disco (.emulator/gcs,
	# gitignored) e o bucket ja' tinha sido criado em testes anteriores. No
	# CI, checkout limpo = emulador sem nenhum bucket (achado no CI real).
	$(PY) -c "from bikeflow.common import storage; storage.ensure_bucket()"
	$(PY) -c "from bikeflow.ingestion.trips.pipeline import ingest_month; print(ingest_month(2025, 2, 'jc'))"
	$(PY) -c "from bikeflow.ingestion.gbfs.snapshot import load_station_information; print(load_station_information())"
	# bronze.station_status so' existe depois de rodar o ciclo de streaming
	# pelo menos 1 vez - sem isso, stg_station_status (e tudo que depende
	# dela) falha no dbt build por a tabela nao existir (achado no CI real).
	# 1o poll e' sempre "cold start" (tabela de CDC vazia, publica tudo) -
	# por isso o max_messages alto aqui, pra pegar uma amostra decente numa
	# chamada so'.
	# ensure_dlq (nao so' ensure_topic/ensure_subscription) liga a DLQ de
	# verdade na subscription principal - achado real, ver messaging.py.
	$(PY) -c "from bikeflow.common import messaging; messaging.ensure_topic(); messaging.ensure_dlq()"
	$(PY) -c "from bikeflow.ingestion.gbfs.poller import poll_once; print('publicadas:', poll_once())"
	$(PY) -c "from bikeflow.streaming.consumer import consume_once; print('consumidas:', consume_once(max_messages=500))"

dbt-debug:  ## Testa a conexao do dbt com o warehouse local
	$(BIN)/dbt debug --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

dbt-deps:  ## Instala os pacotes do dbt (dbt_utils)
	$(BIN)/dbt deps --project-dir $(DBT_DIR)

dbt-freshness: dbt-deps  ## Checa a "idade" do bronze.station_status (warn 15min / error 60min)
	$(BIN)/dbt source freshness --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

dbt-build: dbt-deps  ## Roda os models e testes do dbt (silver + gold)
	$(BIN)/dbt build --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

airflow-up:  ## Sobe emuladores + Airflow (Postgres, init, webserver, scheduler) - pesado, separado do 'make up'
	mkdir -p data
	# 'touch' criaria um arquivo vazio, que o DuckDB rejeita como banco
	# invalido - precisa ser o proprio DuckDB criando (so' roda se o arquivo
	# ainda nao existir).
	test -f data/bikeflow.duckdb || $(PY) -c "import duckdb; duckdb.connect('data/bikeflow.duckdb').close()"
	# Airflow roda como o usuario 'airflow' da imagem (uid fixo, diferente do
	# seu) - o .duckdb vive num bind mount, e qualquer lado (host ou
	# container) que crie o arquivo primeiro tranca o outro fora por
	# permissao (visto na pratica nos dois sentidos). 'touch' + chmod ANTES
	# de subir garante que o arquivo ja' existe permissivo quando o container
	# for abri-lo - depois de criado, so' o dono consegue re-chmodar, entao
	# tem que ser assim, preventivo. Artefatos do dbt (target/logs) vao para
	# dentro do container, nao no bind mount de ./transform.
	chmod 666 data/bikeflow.duckdb
	chmod 777 data
	docker compose --profile airflow up -d --build --wait
	@echo "Airflow em http://localhost:8080 (admin/admin)."

airflow-logs:  ## Acompanha os logs do scheduler (onde as tasks rodam com LocalExecutor)
	docker compose logs -f airflow-scheduler

clean:  ## Remove artefatos de build e cache
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
