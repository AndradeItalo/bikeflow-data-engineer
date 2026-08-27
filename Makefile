.DEFAULT_GOAL := help
.PHONY: help venv install install-dbt up down logs lint fmt test test-all seed-bronze dbt-debug dbt-deps dbt-build clean

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

down:  ## Derruba os emuladores e apaga os volumes
	docker compose down -v

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

seed-bronze:  ## Ingere 1 mes real pequeno (JC) em bronze.trips - para testar dbt sem esperar a NYC inteira
	$(PY) -c "from bikeflow.ingestion.trips.pipeline import ingest_month; print(ingest_month(2025, 2, 'jc'))"

dbt-debug:  ## Testa a conexao do dbt com o warehouse local
	$(BIN)/dbt debug --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

dbt-deps:  ## Instala os pacotes do dbt (dbt_utils)
	$(BIN)/dbt deps --project-dir $(DBT_DIR)

dbt-build: dbt-deps  ## Roda os models e testes do dbt (silver + gold)
	$(BIN)/dbt build --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

clean:  ## Remove artefatos de build e cache
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
