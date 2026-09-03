-- "Saude do pipeline como de agora": freshness + volume + taxa de erro dos
-- testes. NAO usa ref()/source() para meta.dbt_test_results de proposito -
-- essa tabela e' escrita pelo on-run-end (ver persist_test_results.sql),
-- que roda DEPOIS que todo model (este incluido) ja' terminou. Isso
-- significa que este mart SEMPRE reflete a invocacao ANTERIOR do dbt, nunca
-- a atual - um ref() aqui sugeriria uma dependencia fresca que nao existe
-- de verdade. E' o mesmo principio de qualquer health-check real: mostra o
-- ultimo resultado conhecido, nao o futuro.
--
-- pre_hook garante meta.dbt_test_results existir (mesmo vazia) antes do
-- SELECT: numa base zerada, nenhum on-run-end rodou ainda e a tabela nao
-- existe (achado real, ver a macro). Nesse caso invocation_id sai NULL e
-- tests_total sai 0 - correto, e' um cold start de verdade.
{{ config(materialized='table', pre_hook="{{ ensure_dbt_test_results_table() }}") }}

with last_run as (
    select invocation_id
    from meta.dbt_test_results
    order by recorded_at desc
    limit 1
),

test_summary as (
    select
        count(*) as tests_total,
        count(*) filter (where status = 'pass') as tests_passed,
        count(*) filter (where status = 'warn') as tests_warned,
        count(*) filter (where status in ('error', 'fail')) as tests_failed
    from meta.dbt_test_results
    where invocation_id = (select invocation_id from last_run)
),

freshness as (
    -- janela de 1h, nao um lote especifico: robusto pra operacao continua,
    -- nao depende de saber qual foi o ultimo _batch_id.
    select
        percentile_cont(0.95) within group (order by ingestion_lag_minutes)
            as p95_ingestion_lag_minutes,
        max(ingestion_lag_minutes) as max_ingestion_lag_minutes,
        count(*) as station_observations_last_hour
    from {{ ref("fct_station_status") }}
    where observed_at_utc >= now() - interval '1 hour'
),

volume as (
    select
        (select count(*) from {{ ref("fct_trip") }}) as trips_total,
        (select count(*) from {{ ref("fct_station_status") }}) as station_observations_total
)

select
    (select invocation_id from last_run) as invocation_id,
    now() as recorded_at,
    test_summary.tests_total,
    test_summary.tests_passed,
    test_summary.tests_warned,
    test_summary.tests_failed,
    round(test_summary.tests_failed * 1.0 / nullif(test_summary.tests_total, 0), 4)
        as test_error_rate,
    freshness.p95_ingestion_lag_minutes,
    freshness.max_ingestion_lag_minutes,
    freshness.station_observations_last_hour,
    volume.trips_total,
    volume.station_observations_total
from test_summary, freshness, volume
