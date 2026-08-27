{#
    Override do macro padrao do dbt. Sem isso, um model com +schema: silver
    materializaria em `main_silver` (dbt concatena o schema do target com o
    custom schema por padrao) - queremos exatamente `silver`/`gold`, do
    mesmo jeito que bronze/meta ja' existem sem prefixo (ver warehouse.py).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
