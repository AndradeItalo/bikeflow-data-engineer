-- Dimensao gerada (nao vem de nenhuma fonte) - vai do primeiro ao ultimo dia
-- observado em stg_trips. Nao hardcoda o intervalo: senao alguem precisa
-- lembrar de editar isso todo mes que chegar dado novo.
--
-- extract(dow from data): confirmado empiricamente no DuckDB que 0=domingo,
-- 6=sabado (nao e' universal entre bancos, por isso testei antes de assumir).
with bounds as (
    select
        min(date(started_at_utc)) as min_date,
        max(date(started_at_utc)) as max_date
    from {{ ref("stg_trips") }}
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
