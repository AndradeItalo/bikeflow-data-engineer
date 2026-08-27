{#
    Diferenca em segundos entre dois timestamps. Isolado porque o nome da
    funcao E a ordem dos argumentos mudam entre dialetos: DuckDB e'
    date_diff('second', inicio, fim); BigQuery e' TIMESTAMP_DIFF(fim, inicio,
    SECOND) - ordem invertida.
#}
{% macro bf_seconds_diff(start_column, end_column) -%}
    date_diff('second', {{ start_column }}, {{ end_column }})
{%- endmacro %}
