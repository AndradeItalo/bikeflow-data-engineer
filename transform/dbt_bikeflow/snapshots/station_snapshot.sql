{#
    SCD2 de verdade: o dbt compara short_name/name/lat/lon/capacity contra a
    ultima versao registrada. Se algo mudou, fecha a linha antiga
    (dbt_valid_to = agora) e abre uma nova (dbt_valid_from = agora). Se nada
    mudou, nao faz nada. strategy='check' (nao 'timestamp') porque o GBFS nao
    da' um "last modified" por estacao em station_information - so' um
    last_updated do feed inteiro.
#}
{% snapshot station_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='station_id',
        strategy='check',
        check_cols=['short_name', 'name', 'lat', 'lon', 'capacity'],
    )
}}

select * from {{ source('bronze', 'station_information') }}

{% endsnapshot %}
