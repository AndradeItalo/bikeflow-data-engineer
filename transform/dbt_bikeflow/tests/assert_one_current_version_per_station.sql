-- Teste singular: devolve linhas SO' quando algo esta errado (convencao do
-- dbt - teste passa se a query nao devolver nenhuma linha). Aqui: nenhum
-- station_id pode ter mais de 1 versao com is_current = true ao mesmo tempo.
select station_id, count(*) as current_versions
from {{ ref("dim_station") }}
where is_current
group by station_id
having count(*) > 1
