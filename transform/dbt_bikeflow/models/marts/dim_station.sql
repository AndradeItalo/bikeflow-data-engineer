-- station_key e' a chave estavel pro fct_trip. Existe desde ja' (mesmo sem
-- SCD2 ainda) porque quando o GBFS trouxer historico de verdade na Fase 3,
-- station_id deixa de ser unico (varias versoes por estacao) - o fato ja'
-- estara' apontando pra uma chave que sobrevive a' mudanca. Ver ADR-0004.
select
    {{ dbt.hash("station_id") }} as station_key,
    station_id,
    station_name,
    lat,
    lng
from {{ ref("int_trip_stations") }}
