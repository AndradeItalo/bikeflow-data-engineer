-- Dimensao degenerada: so' 2 valores possiveis (ja' validados como
-- accepted_values em stg_trips), entao o proprio valor serve de chave -
-- nao precisa de hash nem tabela de apoio.
select distinct member_casual as member_type
from {{ ref("stg_trips") }}
