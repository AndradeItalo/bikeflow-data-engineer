-- Dimensao gerada, grao de hora (0-23) - suficiente pro grao horario de
-- fct_station_flow_hourly (Fase 3). period_of_day e' so' descritivo de
-- calendario, nao e' regra de negocio de pico de demanda (isso fica pros
-- marts de decisao, nao na dimensao).
with hours as (
    select unnest(generate_series(0, 23)) as hour_of_day
)

select
    hour_of_day as time_key,
    hour_of_day,
    case
        when hour_of_day between 5 and 11 then 'manha'
        when hour_of_day between 12 and 17 then 'tarde'
        when hour_of_day between 18 and 22 then 'noite'
        else 'madrugada'
    end as period_of_day
from hours
