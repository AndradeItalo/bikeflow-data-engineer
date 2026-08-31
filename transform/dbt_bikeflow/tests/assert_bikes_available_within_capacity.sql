-- Qualidade de dado que o PLAN.md pede: 0 <= bikes_available <= capacity.
-- Devolve so' as linhas violando isso (teste passa com 0 linhas).
select
    f.station_id,
    f.observed_at_utc,
    f.num_bikes_available,
    s.capacity
from {{ ref("fct_station_status") }} as f
join {{ ref("dim_station") }} as s on f.station_key = s.station_key
where f.num_bikes_available < 0 or f.num_bikes_available > s.capacity
