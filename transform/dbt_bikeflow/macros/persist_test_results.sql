{#
    DDL isolada numa macro a' parte porque tem 2 chamadores: o on-run-end
    (persist_test_results, abaixo) e o pre_hook de mart_pipeline_health -
    esse ultimo roda ANTES do primeiro on-run-end que essa base ja' teve,
    entao sem isso o mart quebra em warehouse zerado (achado real: 1o
    'make dbt-build' depois de limpar data/ deu Catalog Error, tabela nao
    existia ainda).
#}
{% macro ensure_dbt_test_results_table() %}
    {% if execute %}
        {% do run_query("CREATE SCHEMA IF NOT EXISTS meta") %}
        {% do run_query("
            CREATE TABLE IF NOT EXISTS meta.dbt_test_results (
                invocation_id   VARCHAR,
                test_name       VARCHAR,
                status          VARCHAR,
                failures        BIGINT,
                message         VARCHAR,
                execution_time  DOUBLE,
                recorded_at     TIMESTAMP DEFAULT now()
            )
        ") %}
    {% endif %}
{% endmacro %}

{#
    Roda uma vez no final de todo `dbt build`/`test` (ver on-run-end no
    dbt_project.yml). `results` e' uma lista que o proprio dbt preenche com
    o resultado de cada node executado - aqui filtramos so' os testes.
    invocation_id identifica QUAL execucao gerou cada linha (a mesma ideia
    de _batch_id que ja' usamos na ingestao Python, so' que gerada pelo dbt).
#}
{% macro persist_test_results(results) %}
    {% if execute %}
        {{ ensure_dbt_test_results_table() }}

        {% set rows = [] %}
        {% for result in results %}
            {% if result.node.resource_type == 'test' %}
                {% set message = (result.message or '') | replace("'", "''") %}
                {% set message = message[:200] %}
                {% do rows.append(
                    "('" ~ invocation_id ~ "', '" ~ result.node.name ~ "', '" ~ result.status ~ "', "
                    ~ (result.failures or 0) ~ ", '" ~ message ~ "', " ~ result.execution_time ~ ")"
                ) %}
            {% endif %}
        {% endfor %}

        {% if rows %}
            {% do run_query(
                "INSERT INTO meta.dbt_test_results
                    (invocation_id, test_name, status, failures, message, execution_time)
                 VALUES " ~ rows | join(", ")
            ) %}
        {% endif %}
    {% endif %}
{% endmacro %}
