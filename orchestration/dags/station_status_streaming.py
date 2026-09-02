"""DAG de streaming: poll GBFS -> Pub/Sub -> consome -> bronze.station_status.

Diferente da DAG de viagens (mensal, processa um "mes" do passado), esta e'
quase-tempo-real: agendada a cada 2 min. Nao existe data_interval relevante
aqui - cada run so' pega "o que esta' acontecendo agora" no GBFS, entao
catchup nunca faz sentido (nem esta' configurado) e nao ha' parametro de
ano/mes como na DAG de viagens.

poll e consume ficam na MESMA DAG (nao sao dois componentes totalmente
desacoplados aqui) por simplicidade operacional - o Pub/Sub no meio ja' da'
a folga real: se o consumer atrasar, a mensagem fica na fila, nao se perde.
Rodar os dois em sequencia a cada ciclo so' garante que o que acabou de ser
publicado seja processado logo, sem esperar por acaso de agendamento.

max_active_runs=1: se um ciclo demorar mais que 2 min (rede lenta, etc), o
proximo NAO comeca em cima do anterior - fica na fila do scheduler ate' o
primeiro terminar. Sem isso, dois ciclos rodando ao mesmo tempo poderiam
gerar concorrencia sobre a mesma tabela do DuckDB.

Custo de "cold start" testado de verdade: a primeira execucao (tabela de
CDC vazia) conta TODA estacao como mudada - publicou 2391 mensagens numa
chamada real, ~58s (publish_json bloqueia por mensagem). Ciclos seguintes
com o CDC ja' populado caem para ~1-2s. O consumidor tambem parece limitado
a ~100 mensagens por pull (nao configuravel por nos, aparenta ser do
proprio emulador) - um backlog grande drena ao longo de varios ciclos, nao
de uma vez. Nenhum dos dois e' bug: e' o comportamento esperado de um
sistema que so' fica "leve" depois que o estado de CDC aquece.

dbt_build usa o seletor "+fct_station_status" (o "+" na frente inclui todos
os ANCESTRAIS do node) em vez de um caminho fixo tipo silver/gold - assim
funciona independente de qual DAG rodou primeiro: fct_station_status
depende de dim_station e dim_date, que sao construidos pela DAG de viagens,
nao por esta. Se ainda nao existirem, o dbt constroi tambem; se ja'
existirem, so' atualiza o que mudou.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator


@dag(
    dag_id="station_status_streaming",
    schedule="*/2 * * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(seconds=30),
        # alerta em falha (Fase 4.4). Nota honesta: rodando a cada 2 min,
        # uma falha persistente reenvia e-mail a cada ciclo - nao ha'
        # deduplicacao/throttling aqui. Isso e' escopo de observabilidade
        # (Fase 5), nao desta etapa.
        "email": ["alerts@bikeflow.local"],
        "email_on_failure": True,
        "email_on_retry": False,
    },
    tags=["gbfs", "streaming"],
)
def station_status_streaming() -> None:
    @task
    def poll() -> int:
        """Publica no Pub/Sub as estacoes cujo last_reported mudou desde o ultimo ciclo."""
        from bikeflow.ingestion.gbfs.poller import poll_once

        return poll_once()

    @task
    def consume() -> int:
        """Puxa do Pub/Sub e carrega em bronze.station_status."""
        from bikeflow.streaming.consumer import consume_once

        return consume_once(max_messages=500)

    dbt_build_station_status = BashOperator(
        task_id="dbt_build_station_status",
        bash_command=(
            "dbt build "
            "--project-dir /opt/bikeflow/transform/dbt_bikeflow "
            "--profiles-dir /opt/bikeflow/transform/dbt_bikeflow "
            "--log-path /home/airflow/dbt_logs "
            '--select "+fct_station_status" '
            # cautious (nao o default "eager"): sem isso, testes que
            # referenciam fct_trip entrariam so' por compartilhar dim_station
            # - acoplaria esta DAG a' outra ja' ter rodado antes.
            "--indirect-selection cautious"
        ),
        env={"DBT_TARGET_PATH": "/home/airflow/dbt_target"},
        append_env=True,
    )

    poll() >> consume() >> dbt_build_station_status


station_status_streaming()
