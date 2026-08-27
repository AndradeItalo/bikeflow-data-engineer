-- Dedupe por ride_id (mantem a versao mais recente por _ingested_at) e
-- adiciona as colunas _utc - o resto e' 1:1 com bronze.trips.
with source as (
    select * from {{ source('bronze', 'trips') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by ride_id order by _ingested_at desc
        ) as _dedupe_rank
    from source
)

select
    ride_id,
    rideable_type,
    started_at,
    {{ bf_to_utc('started_at') }} as started_at_utc,
    ended_at,
    {{ bf_to_utc('ended_at') }} as ended_at_utc,
    start_station_name,
    start_station_id,
    end_station_name,
    end_station_id,
    start_lat,
    start_lng,
    end_lat,
    end_lng,
    member_casual,
    _source_file,
    _ingested_at,
    _batch_id
from deduped
where _dedupe_rank = 1
