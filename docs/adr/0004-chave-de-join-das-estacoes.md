# 0004 — Chave de join das estações: dim_station simples antes do GBFS

- **Data:** 2026-08-27
- **Status:** Aceita

## Contexto

O plano original (falha A1) assumia que `station_id` do GBFS casava direto com
o `start_station_id`/`end_station_id` dos CSVs de viagem. Não casa: o GBFS
`station_information` tem um `station_id` numérico longo (ex:
`"2124037125711300644"`) e um campo separado `short_name` (ex: `"2377.01"`);
os CSVs de viagem usam o formato do `short_name` diretamente (confirmado nos
dados reais: `"JC074"`, `"4962.09"`). A chave de join correta é
`short_name` ↔ `start_station_id`/`end_station_id`, não o `station_id` do
GBFS.

**Restrição de sequência:** o GBFS só é ingerido na Fase 3 (Streaming). Na
Fase 2 (Silver + Gold), a única fonte de estação disponível são as próprias
viagens — não há um segundo sistema para reconciliar ainda, então a
resolução de chave de join ("station_xref" como o `PLAN.md` original nomeia)
não é executável hoje.

## Decisão

Construir `dim_station` na Fase 2 diretamente a partir das estações
observadas em `stg_trips` (`int_trip_stations` → `dim_station`), sem
join contra GBFS e sem SCD2. `station_id` na dimensão é exatamente o valor
que já aparece nos CSVs de viagem (já no formato `short_name`).

Introduzido desde já: `station_key` (hash de `station_id`) como chave
substituta estável para `fct_trip`. Quando a Fase 3 trouxer o GBFS e
`dim_station` virar SCD2 de verdade (múltiplas versões por `station_id`,
lat/lon/capacidade historizados), o fato não precisa ser refeito — ele já
aponta para uma chave que sobrevive à mudança.

Achado no processo de construção: `station_id`/`station_name` vêm como
**string vazia** (não `NULL`) quando a bicicleta não foi devolvida numa doca
(perdida ou danificada) — 127 das ~45 mil viagens da amostra real. Filtrar
só `IS NOT NULL` deixava passar uma "estação fantasma" (`station_id = ''`,
hash MD5 de string vazia). Corrigido filtrando `!= ''` também.

## Consequências

- A verdadeira resolução `station_xref` (join `short_name` ↔ GBFS, com taxa
  de match publicada como métrica de qualidade e piso de 95% — como o
  `PLAN.md` original pede) fica para a Fase 3, quando o GBFS existir.
- `dim_station` da Fase 2 é uma dimensão simples e **sabidamente
  incompleta**: só tem estações que já apareceram em pelo menos uma viagem
  (uma estação nova sem viagem ainda não aparece), e não tem capacidade,
  histórico de mudança de nome/local, nem confirmação contra a fonte oficial
  de estações. Isso é aceitável para a Fase 2 porque `fct_trip` só precisa de
  `station_key` para funcionar - não precisa que `dim_station` esteja completa.
- `station_key` estável evita retrabalho em `fct_trip` quando a Fase 3
  reconstruir `dim_station` como SCD2.
