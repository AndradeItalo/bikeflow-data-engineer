-- Mesma ideia de dim_member_type: valor ja' validado em stg_trips vira a
-- propria chave.
select distinct rideable_type
from {{ ref("stg_trips") }}
