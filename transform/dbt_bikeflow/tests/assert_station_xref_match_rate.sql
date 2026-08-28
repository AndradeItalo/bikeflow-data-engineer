-- station_xref real (ADR-0004): trips referencia estacao pelo mesmo formato
-- do GBFS short_name (ex: "3460.01"), nunca pelo station_id do GBFS
-- (UUID/numero). Esse teste mede que fracao dos codigos de estacao vistos em
-- viagens acha correspondencia em dim_station (versao atual) - falha se
-- ficar abaixo do piso de 95% que o PLAN.md pede.
with trip_station_codes as (
    select start_station_id as code
    from {{ ref("stg_trips") }}
    where start_station_id is not null and start_station_id != ''

    union

    select end_station_id as code
    from {{ ref("stg_trips") }}
    where end_station_id is not null and end_station_id != ''
),

current_stations as (
    select short_name
    from {{ ref("dim_station") }}
    where is_current
),

matched as (
    select
        trip_station_codes.code,
        current_stations.short_name is not null as is_matched
    from trip_station_codes
    left join current_stations
        on trip_station_codes.code = current_stations.short_name
),

match_rate as (
    select avg(case when is_matched then 1.0 else 0.0 end) as rate
    from matched
)

select rate
from match_rate
where rate < 0.95
