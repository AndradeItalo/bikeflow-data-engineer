-- materialized='table' (nao incremental) de proposito: gap_minutes usa
-- LAG() sobre o historico inteiro por estacao. Um incremental so' veria o
-- lote novo, e a primeira linha de cada lote calcularia o gap errado (nao
-- enxergaria a ultima observacao do lote anterior). Reconstruir tudo a cada
-- run e' o preco de fazer essa janela certa - aceitavel no volume atual do
-- projeto; otimizar para incremental com lookback fica para quando o volume
-- justificar a complexidade extra.
--
-- join por station_id (nao short_name): station_status usa o MESMO
-- station_id nativo do GBFS que station_information usa - diferente de
-- viagens, aqui nao ha' mismatch de formato (ver Fase 3, achado do
-- station_id misturar UUID/numero, mas consistente entre os dois feeds).
with status as (
    select
        *,
        lag(observed_at_utc) over (
            partition by station_id order by observed_at_utc
        ) as previous_observed_at_utc
    from {{ ref("stg_station_status") }}
)

select
    station.station_key,
    status.station_id,
    status.observed_at_utc,
    date_dim.date_key,
    time_dim.time_key,
    status.num_bikes_available,
    status.num_bikes_disabled,
    status.num_docks_available,
    status.num_docks_disabled,
    status.is_installed,
    status.is_renting,
    status.is_returning,
    status.num_ebikes_available,
    {{ bf_seconds_diff("status.previous_observed_at_utc", "status.observed_at_utc") }} / 60.0
        as gap_minutes
from status
left join {{ ref("dim_station") }} as station
    on status.station_id = station.station_id and station.is_current
left join {{ ref("dim_date") }} as date_dim
    on date(status.observed_at_utc) = date_dim.date_day
left join {{ ref("dim_time") }} as time_dim
    on extract(hour from status.observed_at_utc) = time_dim.hour_of_day
