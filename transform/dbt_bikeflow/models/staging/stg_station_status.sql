-- Dedupe por (station_id, last_reported): a mesma leitura pode ser
-- reprocessada (retry de mensagem no Pub/Sub, retry de task no Airflow) -
-- mantem so' uma linha por observacao distinta. last_reported vem como
-- epoch (segundos, UTC pela spec do GBFS) - convertido pra TIMESTAMP naive
-- em UTC aqui (bronze fica cru, silver tipa). is_installed/is_renting/
-- is_returning vem como 0/1 no feed real, viram boolean aqui.
with source as (
    select * from {{ source("bronze", "station_status") }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by station_id, last_reported order by _ingested_at desc
        ) as _dedupe_rank
    from source
)

select
    station_id,
    to_timestamp(last_reported) at time zone 'UTC' as observed_at_utc,
    num_bikes_available,
    num_bikes_disabled,
    num_docks_available,
    num_docks_disabled,
    is_installed = 1 as is_installed,
    is_renting = 1 as is_renting,
    is_returning = 1 as is_returning,
    num_ebikes_available,
    _ingested_at,
    _batch_id
from deduped
where _dedupe_rank = 1
