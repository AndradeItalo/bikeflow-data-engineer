# SLO de freshness — streaming (GBFS → gold)

## Definição

**p95 da latência de ingestão < 5 minutos**, do momento em que o GBFS reporta
uma mudança de status de estação (`last_reported`) até a linha estar
disponível em `gold.fct_station_status`.

## Como é medido

`fct_station_status.ingestion_lag_minutes` = `_ingested_at` (quando a
mensagem foi consumida e carregada em `bronze.station_status`) menos
`observed_at_utc` (o `last_reported` do GBFS, convertido pra UTC).

O tempo entre `bronze` e o mart em si (`fct_station_status`) não entra na
conta separadamente porque é o próprio `dbt build`, que roda em menos de 2
segundos na mesma execução da DAG — desprezível frente à escala de minutos
do poll (2 em 2 min).

```sql
select
    count(*) as n,
    avg(ingestion_lag_minutes) as media_min,
    percentile_cont(0.95) within group (order by ingestion_lag_minutes) as p95_min,
    max(ingestion_lag_minutes) as max_min
from gold.fct_station_status
where _batch_id = '<batch de interesse>'
```

## Primeira medição real (2026-09-02)

Uma leva de 100 observações reais do GBFS, consumida numa única execução do
ciclo poll→consume→dbt:

| Métrica | Valor |
|---|---|
| n | 100 |
| mínimo | 3,68 min |
| média | 3,85 min |
| **p95** | **4,02 min** |
| máximo | 4,03 min |

**Dentro da meta (p95 < 5 min).**

### Ressalva honesta

Essa é uma medição de **uma sessão de teste curta** (poucos ciclos manuais
de poll/consume rodados em sequência), não de produção rodando de forma
contínua por dias. O número real depende de: o quão perto o poller está do
próximo ciclo de 2 min quando uma mudança acontece no GBFS (na pior hipótese,
quase 2 min só de espera pelo próximo poll), do backlog do consumidor (o
emulador limita a ~100 mensagens por `pull()` — um backlog grande atrasa
quem está no fim da fila, ver `docs/findings-log.md`), e da variação natural
de quando o próprio GBFS atualiza `last_reported`.

Monitorar isso de forma contínua (não só uma medição pontual) é o que
`mart_pipeline_health` (Fase 5.4) formaliza — agregando essa mesma coluna
por janela de tempo, não por lote de teste.
