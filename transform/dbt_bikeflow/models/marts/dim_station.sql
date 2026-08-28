-- SCD2 de verdade a partir do snapshot (ver ADR-0004 e o snapshot
-- station_snapshot). station_key agora e' por VERSAO (station_id +
-- dbt_valid_from), nao por estacao - e' isso que faz SCD2 funcionar: cada
-- versao historica precisa da propria chave. fct_trip junta por short_name
-- (o codigo real que aparece nas viagens) e filtra so' a versao atual.
select
    {{ dbt.hash("station_id || '|' || cast(dbt_valid_from as varchar)") }} as station_key,
    station_id,
    short_name,
    name as station_name,
    lat,
    lon as lng,
    capacity,
    dbt_valid_from as valid_from,
    dbt_valid_to as valid_to,
    dbt_valid_to is null as is_current
from {{ ref("station_snapshot") }}
