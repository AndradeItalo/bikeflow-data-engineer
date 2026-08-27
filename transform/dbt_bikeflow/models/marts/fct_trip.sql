{{
    config(
        materialized='incremental',
        unique_key='ride_id',
        incremental_strategy='merge',
    )
}}

-- NAO usar partition_by/cluster_by aqui: ao contrario do que o PLAN.md
-- original assumia, o adapter do DuckDB NAO ignora essas chaves - ele tem
-- semantica propria pra elas (particionamento de arquivo Hive-style) e quebra
-- a build se receber o formato do BigQuery. Isso fica para a Fase 7
-- (Validacao BigQuery), com um bloco condicional no config() checando o
-- adapter em uso - nao da' pra compartilhar a mesma chave entre os dois.
with trips as (
    select * from {{ ref("stg_trips") }}
    {% if is_incremental() %}
    where started_at_utc > (select max(started_at_utc) from {{ this }})
    {% endif %}
)

select
    trips.ride_id,
    date(trips.started_at_utc) as trip_date,
    trips.started_at_utc,
    trips.ended_at_utc,
    start_station.station_key as start_station_key,
    end_station.station_key as end_station_key,
    start_date.date_key as start_date_key,
    end_date.date_key as end_date_key,
    start_time.time_key as start_time_key,
    end_time.time_key as end_time_key,
    trips.member_casual as member_type,
    trips.rideable_type,
    {{ bf_seconds_diff("trips.started_at_utc", "trips.ended_at_utc") }} as trip_duration_sec,
    {{ bf_haversine_km("trips.start_lat", "trips.start_lng", "trips.end_lat", "trips.end_lng") }}
        as distance_km
from trips
left join {{ ref("dim_station") }} as start_station
    on trips.start_station_id = start_station.station_id
left join {{ ref("dim_station") }} as end_station
    on trips.end_station_id = end_station.station_id
left join {{ ref("dim_date") }} as start_date
    on date(trips.started_at_utc) = start_date.date_day
left join {{ ref("dim_date") }} as end_date
    on date(trips.ended_at_utc) = end_date.date_day
left join {{ ref("dim_time") }} as start_time
    on extract(hour from trips.started_at_utc) = start_time.hour_of_day
left join {{ ref("dim_time") }} as end_time
    on extract(hour from trips.ended_at_utc) = end_time.hour_of_day
