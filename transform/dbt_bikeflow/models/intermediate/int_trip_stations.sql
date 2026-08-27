-- Estacoes distintas observadas em viagens (origem + destino), com o nome/
-- lat/lng mais recentes por station_id. Base de dim_station ate' o GBFS
-- chegar na Fase 3 - ver ADR-0004.
--
-- station_id/name vem como STRING VAZIA (nao NULL) quando a bicicleta nao
-- foi devolvida numa doca (perdida/danificada) - confirmado no dado real:
-- 127 viagens com end_station_id = ''. Filtrar so' NULL deixaria passar uma
-- "estacao fantasma".
with start_stations as (
    select
        start_station_id as station_id,
        start_station_name as station_name,
        start_lat as lat,
        start_lng as lng,
        started_at_utc as observed_at
    from {{ ref('stg_trips') }}
    where start_station_id is not null and start_station_id != ''
),

end_stations as (
    select
        end_station_id as station_id,
        end_station_name as station_name,
        end_lat as lat,
        end_lng as lng,
        ended_at_utc as observed_at
    from {{ ref('stg_trips') }}
    where end_station_id is not null and end_station_id != ''
),

unioned as (
    select * from start_stations
    union all
    select * from end_stations
),

ranked as (
    select
        *,
        row_number() over (
            partition by station_id order by observed_at desc
        ) as _recency_rank
    from unioned
)

select
    station_id,
    station_name,
    lat,
    lng
from ranked
where _recency_rank = 1
