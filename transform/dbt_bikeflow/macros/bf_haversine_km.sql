{#
    Distancia em linha reta (km) entre dois pontos lat/lng, formula de
    haversine. sin/cos/asin/sqrt/radians sao funcoes SQL padrao, existem tanto
    no DuckDB quanto no BigQuery com a mesma assinatura - isolado em macro
    mesmo assim, pra qualquer divergencia futura ficar num lugar so'.
    NULL se end_lat/end_lng forem NULL (viagem sem estacao de destino).
#}
{% macro bf_haversine_km(lat1, lng1, lat2, lng2) -%}
    (2 * 6371 * asin(sqrt(
        pow(sin(radians({{ lat2 }} - {{ lat1 }}) / 2), 2)
        + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }}))
        * pow(sin(radians({{ lng2 }} - {{ lng1 }}) / 2), 2)
    )))
{%- endmacro %}
