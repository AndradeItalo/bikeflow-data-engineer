-- Dimensao gerada (nao vem de nenhuma fonte) - vai do primeiro ao ultimo dia
-- observado em QUALQUER fonte com data (viagens + status de estacao). Nao
-- hardcoda o intervalo: senao alguem precisa lembrar de editar isso toda
-- vez que chegar dado novo. station_status entra aqui porque suas
-- observacoes sao de "agora" - fora do intervalo historico das viagens - e
-- sem isso o join em fct_station_status ficaria com date_key nulo.
--
-- extract(dow from data): confirmado empiricamente no DuckDB que 0=domingo,
-- 6=sabado (nao e' universal entre bancos, por isso testei antes de assumir).
with trip_dates as (
    select date(started_at_utc) as observed_date from {{ ref("stg_trips") }}
    union
    select date(ended_at_utc) as observed_date from {{ ref("stg_trips") }}
),

station_status_dates as (
    select date(observed_at_utc) as observed_date from {{ ref("stg_station_status") }}
),

bounds as (
    select
        min(observed_date) as min_date,
        max(observed_date) as max_date
    from (
        select * from trip_dates
        union all
        select * from station_status_dates
    )
),

calendar as (
    -- generate_series com interval devolve TIMESTAMP, nao DATE - cast de volta
    select cast(unnest(generate_series(
        (select min_date from bounds),
        (select max_date from bounds),
        interval 1 day
    )) as date) as date_day
)

select
    cast(strftime(date_day, '%Y%m%d') as integer) as date_key,
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    extract(day from date_day) as day,
    extract(dow from date_day) as day_of_week,
    strftime(date_day, '%A') as day_name,
    extract(dow from date_day) in (0, 6) as is_weekend
from calendar
