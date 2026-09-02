"""DAG de ingestao de viagens: resolve -> download -> bronze -> silver -> gold.

Primeira DAG do projeto - conceitos explicados aqui, nao vou repetir nas
proximas:

DAG (Directed Acyclic Graph) so' declara O GRAFO de tasks e suas
dependencias - "isso depende daquilo". Ela nao executa nada sozinha: quem
decide QUANDO rodar e' o scheduler (baseado no `schedule`), quem EXECUTA de
fato e' o LocalExecutor (subprocesso do proprio container do scheduler).

data_interval_start (o "mes que esta DAG run processa") e' DIFERENTE do dia
em que ela roda de verdade. Isso e' o que permite BACKFILL: rodar HOJE uma
DAG run "como se fosse" janeiro/2024, processando esse mes especifico, nao o
mes atual.

XCom e' como uma task passa um valor pequeno pra proxima: o retorno de uma
funcao @task (aqui, o source_key resolvido no download) fica disponivel pra
quem chamar ela depois, sem voce escrever nada explicito de serializacao.

catchup=False de proposito: catchup=True faria o Airflow tentar rodar TODOS
os meses perdidos desde start_date de uma vez (24+ downloads reais) assim
que a DAG fosse ativada. Pra rodar um mes especifico manualmente, use
SEMPRE inicio/fim explicitos, nunca uma data solta:
    airflow dags backfill -s 2024-01-01 -e 2024-02-01 trips_ingestion

NAO use `airflow dags test trips_ingestion <data>` pra "simular o mes X" -
testei e da' errado: a CLI interpreta a data em UTC, mas o schedule desta
DAG e' em America/New_York (UTC-5); a diferenca de fuso empurra o calculo
pro mes ERRADO quando a data nao cai exatamente no limite (`dags test
2025-03-01` processou JANEIRO/2025, nao fevereiro). `dags backfill -s/-e`
com datas explicitas nao tem essa ambiguidade - foi o que validei de fato.

O "quality_gate" que o PLAN.md menciona entre silver e gold nao e' uma task
separada aqui - e' a propria dependencia do grafo: dbt build --select
silver ja' roda os testes daquela camada inline, e se algum falhar (exit
code != 0), o Airflow nao deixa a task de gold comecar. O gate E a aresta,
nao uma task nova.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

DBT_PROJECT_DIR = "/opt/bikeflow/transform/dbt_bikeflow"
# target/logs do dbt vao para DENTRO do container, nao no bind mount de
# ./transform: o bind mount e' dono do uid do host, o container do Airflow
# nao consegue escrever ali (ver docs/findings-log.md, Fase 4).
DBT_ENV = {"DBT_TARGET_PATH": "/home/airflow/dbt_target"}
DBT_BASE_CMD = (
    f"dbt build --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR} "
    "--log-path /home/airflow/dbt_logs"
)


@dag(
    dag_id="trips_ingestion",
    schedule="@monthly",
    start_date=pendulum.datetime(2024, 1, 1, tz="America/New_York"),
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=5),
        # alerta em falha (Fase 4.4): dispara so' depois de esgotar os
        # retries acima. SMTP aponta pro Mailpit (docker-compose), captura
        # de verdade em vez de mockar "confiamos que o email foi enviado".
        "email": ["alerts@bikeflow.local"],
        "email_on_failure": True,
        "email_on_retry": False,
    },
    tags=["trips", "batch"],
    # group e' parametro (nao hardcoded) de proposito: da' pra testar/rodar
    # com "jc" (arquivo pequeno, ~1-2MB) em vez de esperar um mes inteiro de
    # NYC (300MB+) toda vez que for so' validar o pipeline.
    params={"group": Param("nyc", enum=["nyc", "jc"])},
)
def trips_ingestion() -> None:
    @task
    def download(
        params: dict | None = None, data_interval_start: pendulum.DateTime | None = None
    ) -> str:
        """Resolve e baixa o arquivo do mes desta DAG run. Devolve source_key (via XCom)."""
        from bikeflow.ingestion.trips.downloader import download_trip_file
        from bikeflow.ingestion.trips.resolver import resolve_trip_file

        assert data_interval_start is not None and params is not None
        group = params["group"]
        year, month = data_interval_start.year, data_interval_start.month
        resolved = resolve_trip_file(year, month, group)
        download_trip_file(year, month, group, batch_id=data_interval_start.to_date_string())
        return resolved.key

    @task
    def load_bronze(source_key: str, data_interval_start: pendulum.DateTime | None = None) -> int:
        """Normaliza o zip da landing (Parquet em chunks) e carrega em bronze.trips."""
        from bikeflow.ingestion.trips.normalizer import load_trip_file_to_bronze

        assert data_interval_start is not None
        return load_trip_file_to_bronze(source_key, batch_id=data_interval_start.to_date_string())

    dbt_build_silver = BashOperator(
        task_id="dbt_build_silver",
        bash_command=(
            f"{DBT_BASE_CMD} "
            '--select "path:models/staging" "path:models/intermediate" "station_snapshot"'
        ),
        env=DBT_ENV,
        append_env=True,  # sem isso, env= SUBSTITUI o ambiente inteiro (perderia PATH, config do bikeflow)
    )

    dbt_build_gold = BashOperator(
        task_id="dbt_build_gold",
        bash_command=f'{DBT_BASE_CMD} --select "path:models/marts"',
        env=DBT_ENV,
        append_env=True,
    )

    source_key = download()
    load_bronze(source_key) >> dbt_build_silver >> dbt_build_gold


trips_ingestion()
