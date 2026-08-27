{#
    Converte um timestamp local ingenuo (America/New_York, o que os CSVs de
    viagem trazem) para UTC, respeitando o horario de verao.

    Isolado num macro porque o dialeto muda entre DuckDB e BigQuery (falha
    A7/B do PLAN.md: comparar local ingenuo com UTC direto erra 4-5h e da'
    "horario de pico" errado).

    Limitacao conhecida: na 1h que se repete na virada de novembro (ex:
    2024-11-03 01:30, que acontece uma vez em EDT e outra em EST), nao ha'
    como saber pela fonte qual das duas ocorrencias e' a real - o ICU do
    DuckDB resolve para o lado padrao (EST). Afeta no maximo 1h/ano.
#}
{% macro bf_to_utc(column_name) -%}
    ({{ column_name }} AT TIME ZONE 'America/New_York') AT TIME ZONE 'UTC'
{%- endmacro %}
