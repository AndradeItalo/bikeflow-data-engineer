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

## Atualização (Fase 3, 2026-08-27)

O GBFS chegou. `dim_station` foi reconstruída como SCD2 de verdade via `dbt
snapshot` (`station_snapshot`, strategy `check` sobre `short_name`/`name`/
`lat`/`lon`/`capacity`) a partir de `bronze.station_information`.
`station_key` agora é por **versão** (`station_id` + `dbt_valid_from`), não
mais por estação — é assim que SCD2 funciona de verdade, cada versão
histórica precisa da própria chave. `fct_trip` continua com o mesmo formato
de join, só trocando a coluna: `short_name` em vez de `station_id`, travado
em `is_current = true` para não gerar fan-out entre versões históricas.

O `station_xref` real (teste `assert_station_xref_match_rate`, piso de 95%
do `PLAN.md`) passou com **95,24%** de match (126 códigos distintos vistos em
viagens, ~6 sem correspondência) — perto o suficiente do piso pra valer
registrar por quê:

1. **As viagens são de fevereiro/2025; o snapshot do GBFS é de agora.**
   Estações fecham, são renomeadas ou renumeradas nesse intervalo — 100% de
   match entre um histórico e um snapshot atual nunca é esperado.
2. **Achado novo, fora do escopo que o `PLAN.md` documentava**: dois dos
   códigos sem match têm prefixo `HB` (`HB102`, `HB508`) — **Hoboken**, uma
   terceira área de operação da Citi Bike (além de NYC e Jersey City) que o
   `PLAN.md` nunca menciona no "Escopo de dados". Não é um bug do resolver;
   é uma lacuna de escopo que só apareceu rodando o teste de match contra
   dado real.

Nenhuma ação tomada sobre a lacuna de Hoboken agora — registrado aqui e no
`docs/findings-log.md` para decisão futura (ampliar escopo ou declarar fora
de escopo explicitamente, em vez de ignorar).

**Nota de correção:** logo depois desta análise, uma recarga de
`bronze.station_information` interrompida no meio (sem transação) derrubou a
taxa medida para 45% — não era drift real, era corrupção de dado causada por
`load_station_information()` não ser atômica (`DELETE` aplicado, só parte do
`INSERT` novo concluído). Corrigido envolvendo a operação em
`BEGIN`/`COMMIT`/`ROLLBACK` explícitos e trocando o loop linha a linha por
`executemany`. Depois da correção, a taxa voltou a bater os mesmos 95,24% -
confirma que o número original era real, não sorte.
