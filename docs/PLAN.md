# BikeFlow — Revisão crítica do plano e reescrita (trilha local-first)

## Context

O repositório está vazio (só `README.md` + `plano.md` não versionado). O `plano.md` atual é uma boa
ideia de negócio com uma arquitetura genérica: lista serviços GCP em caixinhas, mas não define
contratos de dados, chaves de join, idempotência, custo ou critério de "pronto". Vários pontos
quebrariam na primeira execução real.

**Restrição nova e decisiva:** o usuário não conseguiu ativar o Cloud Billing (o Google exige
pré-pagamento de R$ 200 no fluxo via PIX) e optou por **não usar cartão de crédito**. Logo,
**não há acesso a GCP pago no momento** — nem Cloud Storage, nem BigQuery com DML, nem Pub/Sub real.

Decisões do usuário:
- **Orçamento:** R$ 0. Nenhum recurso GCP faturável.
- **Objetivo:** profundidade de engenharia primeiro, amplitude de serviços depois.
- **Prazo:** sem prazo — fases incrementais, cada uma tagueada no Git.

**Estratégia:** construir o projeto inteiro **local-first**, com emuladores oficiais e os mesmos SDKs
do Google, de forma que a migração para GCP seja troca de variável de ambiente — não reescrita.
Isso não é um plano B envergonhado: um repositório que um tech lead clona e roda inteiro com
`make up`, sem precisar de conta GCP, vale **mais** em portfólio que um dashboard hospedado.

**Resultado esperado:** substituir `plano.md` por um plano executável que qualquer tech lead leia em
10 minutos e conclua "essa pessoa sabe fazer engenharia de dados".

---

## Parte 1 — Falhas encontradas no plano atual

### A. Falhas que quebrariam o projeto na prática (bugs, não opinião)

| # | Falha | Evidência | Correção |
|---|---|---|---|
| A1 | **Chave de join errada entre batch e streaming.** O plano assume que `station_id` do GBFS casa com o dos arquivos de viagem. | GBFS retorna `"station_id": "2124037125711300644"` e `"short_name": "2377.01"`; os CSVs de viagem usam o formato `2377.01`. | Join por `short_name` ↔ `start_station_id`/`end_station_id`, com fallback por nome normalizado + distância geográfica. Materializar como `stg_station_xref` e **publicar a taxa de match como métrica de qualidade**. |
| A2 | **`dim_bike` não tem fonte.** O schema atual (pós-fev/2021) removeu `bikeid`; só existe `rideable_type`. | Schema novo: `ride_id, rideable_type, started_at, ended_at, start_station_name, start_station_id, ..., member_casual`. | Eliminar `dim_bike`. Usar `rideable_type` como dimensão degenerada. O nome "BikeFlow" continua válido — o fluxo é de docas, não de bicicletas rastreáveis. |
| A3 | **URL de download hardcoded quebra.** O padrão real alterna `.zip` e `.csv.zip`, tem prefixo `JC-` e arquivos **anuais** antes de 2024. | Listagem de `s3://tripdata`: `202604-citibike-tripdata.zip` vs `202605-citibike-tripdata.csv.zip`, `JC-2026*`. | Listar o índice do bucket e resolver o nome por regex, com fallback entre extensões. Registrar em `ingestion_manifest`. |
| A4 | **URL do GBFS desatualizada.** `gbfs.citibikenyc.com/gbfs/en/station_status.json` é legado. | Auto-discovery aponta para `https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_status.json` (GBFS v1.1). | Resolver sempre via `gbfs.json` (auto-discovery) — é a prática da spec e sobrevive a mudança de host. |
| A5 | **Warehouse não lê `.zip`.** O bucket do plano guarda `tripdata.zip` mas o texto promete "arquivos Parquet". | Contradição interna (l. 118 vs 390-402). | Camada `landing/` (zip original, imutável, para lineage) → job de normalização → Parquet particionado → carga em `bronze.trips`. |
| A6 | **Download carrega o arquivo inteiro em RAM** (`response.content`) — arquivos mensais passam de 1 GB. | Código do plano, l. 368-374. | `stream=True` + upload em chunks; conversão para Parquet em lotes com `pyarrow`. |
| A7 | **Fuso horário ignorado.** CSVs de viagem trazem timestamp **local ingênuo** (America/New_York, com DST); GBFS traz `last_reported` em **epoch UTC**. | Comparar direto gera erro de 4-5 h; "horário de pico" sai errado. | Armazenar tudo em TIMESTAMP UTC + colunas derivadas `local_date`/`local_hour` em `America/New_York`. Teste unitário cobrindo os dois dias de virada de DST. |
| A8 | **`estimated_bikes_available` é desnecessário.** O GBFS entrega `num_bikes_available` exato. | O campo "estimado" é herança do simulador fictício. | Usar o valor real. Reservar "estimado/previsto" só para a saída do modelo. |

### B. Falhas de arquitetura

| # | Falha | Impacto | Correção |
|---|---|---|---|
| B1 | **O plano inteiro depende de GCP faturável** (Composer, Dataflow, GCS, BigQuery com MERGE). | Com R$ 0 de billing, o plano original é **inexecutável hoje**. | Arquitetura local-first com emuladores oficiais + tabela de equivalência local↔GCP. Ver Parte 2. |
| B2 | **Dataflow é overkill para o caso de uso.** O pipeline só faz passthrough JSON→warehouse. | Complexidade e custo sem ganho; um revisor sênior percebe. | Local: consumidor Python. Em GCP: **Pub/Sub BigQuery Subscription** (nativo, sem worker). Dataflow só se houver janela/agregação real. Registrar em ADR — saber *não* usar um serviço vale mais que usar. |
| B3 | **Duas fontes de streaming contraditórias.** O plano tem um simulador `bike_rented`/`bike_returned` **e** o GBFS real. | Dado sintético desvaloriza o portfólio; o próprio plano admite que o simulador é desnecessário. | **Remover o simulador como fonte.** Mantê-lo só como ferramenta de teste de carga, rotulada em `tools/`. |
| B4 | **Volume de streaming não dimensionado.** ~2,2 mil estações × 1 poll/min = ~3,2 M msg/dia. | Estouro de disco local e de custo quando migrar. | Poll a cada 2-5 min + **publicar só estações cujo `last_reported` mudou** (CDC). Cai ~10x. Tabela de volume no README. |
| B5 | **Terraform e CI/CD só aparecem na tabela de stack** — nunca nas fases. | Se entram no fim, o resto não é reprodutível. | CI na Fase 0. Terraform escrito e **validado no CI** (`fmt`/`validate`/`tflint`) desde a Fase 1, com `apply` explicitamente pendente de billing — declarar é melhor que fingir. |
| B6 | **"Dataform / dbt" — o plano não escolhe.** | Indecisão visível no repo. | **dbt-core** (roda local, testável, é o que aparece nas vagas). Registrar o porquê em ADR; Dataform citado como alternativa avaliada e descartada (exige BigQuery faturável). |
| B7 | **"Real-Time Dashboard" não é real-time.** | Promessa que o projeto não cumpre. | Chamar de *near-real-time*, declarar **SLO de freshness** (p95 < 5 min do `last_reported` ao mart) e medi-lo. |

### C. Lacunas de engenharia (o que separa "projeto de curso" de "portfólio")

1. **Idempotência é citada, nunca especificada.** Falta o mecanismo: tabela `ingestion_manifest` (url, etag, bytes, md5, row_count, status, batch_id) + carga por partição com truncate + `MERGE` por `ride_id`.
2. **Sem colunas de linhagem** (`_source_file`, `_ingested_at`, `_batch_id`, `_dbt_invocation_id`).
3. **"quality_check" é uma caixinha.** Falta: quais testes, o que acontece quando falham (falha a DAG? quarentena?), e onde o resultado fica visível.
4. **Evolução de schema não tratada.** Fev/2021 mudou o schema por completo. Decidir escopo (2024-01 em diante) e declarar o legado.
5. **Sem estratégia de testes de código** — nenhum pytest, mock de HTTP, lint ou pre-commit.
6. **Sem ambientes** (dev/prod), sem convenção de nomes, sem estrutura de repositório.
7. **Sem contrato dos KPIs de engenharia.** "Latência do pipeline", "eventos inválidos" não têm tabela de origem.
8. **Monitoramento sem alertas.** Falta DLQ e política de alerta.
9. **ML ingênuo.** Cita "weather" sem fonte, sem baseline, sem métrica, sem split temporal, sem consumo do resultado.
10. **Sem documentação como produto** — sem README de verdade, sem ADRs, sem dicionário de dados, sem runbook.
11. **Vocabulário de camadas inconsistente.** O plano usa quatro nomenclaturas para as mesmas camadas: `RAW/BRONZE → SILVER/GOLD` (l. 43-52), `RAW → Trusted → Analytics` (l. 105-111), `Raw/Trusted/Gold` (l. 277) e `Bronze → Silver/Gold` (l. 648-654).
12. **Licença ignorada.** A política do Citi Bike permite analisar e redistribuir *dentro do seu produto*, mas **proíbe publicar os dados como dataset standalone** e veda sugerir afiliação. Restringe o que vai para o GitHub e para o dashboard público.
13. **Diretório vazio `aa/`** no repo — remover.

### D. A oportunidade que o plano quase encontrou (o diferencial real)

O plano acerta ao dizer que "o GBFS não é pensado para histórico, então seu pipeline constrói esse
histórico". Falta o passo seguinte:

> Comparando a variação observada de bicicletas numa estação (GBFS) com a variação **explicada por
> viagens** (retiradas − devoluções), a diferença é **rebalanceamento manual por caminhão** ou
> bicicleta com defeito.

Dá para **inferir as operações de redistribuição que a empresa já executa**, sem ter os dados internos
dela — e então validar a recomendação do projeto contra o comportamento real ("o modelo teria
recomendado o mesmo caminhão que a operação de fato mandou?"). Isso é incomparavelmente mais forte
que um dashboard com semáforo.

---

## Parte 2 — Arquitetura local-first

Todo componente usa **o SDK oficial do Google** apontado para um emulador. Migrar para GCP é trocar
variável de ambiente, não reescrever código.

```
           BATCH (mensal)                       NEAR-REAL-TIME (a cada 2 min)
      Citi Bike S3 tripdata                   GBFS auto-discovery (gbfs.json)
            │ job: resolve + fetch                  │ job: poll + filtro CDC
            ▼                                       ▼
LANDING   fake-gcs-server                   fake-gcs-server (snapshot .json.gz)
          landing/trips/*.zip                       │ Pub/Sub emulator ──► DLQ
            │ job: normalize (pyarrow)              │ consumidor Python
            ▼                                       ▼
BRONZE    bronze.trips  ◄── load             bronze.station_status   bronze.station_information
            │  (tipado, 1:1 com a fonte, + _source_file/_ingested_at/_batch_id)
            ▼
SILVER    dbt: dedupe, UTC, station_xref, quarentena  ──►  silver.* (+ _rejected)
            │
            ▼
GOLD      dbt: dim_station (SCD2), dim_date, fct_trip, fct_station_status,
          fct_station_flow_hourly, mart_rebalancing_recommendation
            │
   ┌────────┼────────┐                        META: meta.ingestion_manifest,
   ▼        ▼        ▼                              meta.dbt_test_results,
Operacional Analítico Engenharia ──► Evidence.dev    meta.pipeline_health
Orquestração: Airflow (docker-compose)  |  IaC: Terraform (validado no CI)  |  CI: GitHub Actions
```

### Tabela de equivalência local ↔ GCP

Esta tabela vai no README. É ela que prova que o projeto é sobre GCP mesmo rodando local.

| Papel | Local (hoje, R$ 0) | GCP (quando destravar) | O código muda? |
|---|---|---|---|
| Object storage | `fsouza/fake-gcs-server` | Cloud Storage | **Não** — só `STORAGE_EMULATOR_HOST` |
| Mensageria | Pub/Sub emulator (oficial, `gcloud beta emulators pubsub`) | Pub/Sub | **Não** — só `PUBSUB_EMULATOR_HOST` |
| Warehouse | DuckDB | BigQuery | Target do dbt; SQL de dialeto isolado em macros |
| Sink de streaming | consumidor Python → DuckDB | **BigQuery Subscription** (nativo, sem worker) | Troca de componente (~80 linhas a menos) |
| Orquestração | **Airflow** via docker-compose | Cloud Composer | **Não** — DAG idêntica |
| Compute de job | container local | Cloud Run Job | **Não** — mesmo Dockerfile |
| Dashboard | Evidence.dev (estático, publicável grátis) | Looker Studio | Recriado |
| IaC | — | Terraform | Escrito e validado no CI desde já |

Dois ganhos que a restrição de orçamento produziu:

- **Airflow de verdade, de graça.** Antes o Composer era proibitivo (cobra por DCU-hora mesmo ocioso) e eu ia ter que substituí-lo por Cloud Workflows. Local, o Airflow roda sem custo e é o orquestrador mais reconhecido em vaga.
- **Dashboard público clicável.** Evidence.dev gera site estático a partir do DuckDB e publica de graça no GitHub Pages. Um recrutador clica em um link em vez de olhar screenshot. (Publicar só agregados — a licença do Citi Bike proíbe republicar os dados brutos.)

### Validação do dialeto BigQuery sem cartão

Risco real da trilha local: escrever SQL que funciona no DuckDB e quebra no BigQuery. Mitigação em
duas camadas:

1. **Macros de dialeto** — toda função de data/timestamp passa por macro (`{{ bf_to_utc() }}`, `{{ bf_local_hour() }}`); `partition_by`/`cluster_by` ficam em `config()` que o DuckDB ignora e o BigQuery usa.
2. **BigQuery Sandbox como target de validação** — o sandbox é grátis e **não pede cartão**. Roda `dbt build --target sandbox --exclude config.materialized:incremental` sobre uma amostra (1 mês). Limites verificados na doc oficial: 10 GB storage, 1 TB query/mês, tabelas expiram em 60 dias, **sem DML** (por isso só `table`/`view`, que são DDL) e **sem streaming**. Suficiente para provar que o dialeto está correto.

---

## Camadas de dados — medalhão, com duas correções

**1. Medalhão e Kimball são ortogonais, não alternativas.** Medalhão descreve o *grau de refinamento*;
Kimball descreve o *formato do modelo* na camada final. O gold é dimensional (`dim_`/`fct_`).

**2. Existe uma camada 0.** O `.zip` não é bronze: é *landing*, imutável e não consultável, que existe
para replay e lineage. Bronze é a primeira camada consultável.

| Camada | Onde vive | Conteúdo | Materialização | Retenção |
|---|---|---|---|---|
| **Landing** | `bikeflow-lake/landing/` (fake-gcs → GCS) | zip original + snapshot GBFS (`.json.gz`) | arquivo, write-once | lifecycle → Nearline 30 d |
| **Bronze** | schema `bikeflow_bronze` | tipado, 1:1 com a fonte, **zero regra de negócio**, + linhagem | load job / consumidor de streaming | partição expira em 180 d |
| **Silver** | `bikeflow_silver` | deduplicado, UTC, `station_xref` resolvido, quarentena aplicada | dbt — pastas `staging/` + `intermediate/` | sem expiração |
| **Gold** | `bikeflow_gold` | Kimball + marts de decisão | dbt — pasta `marts/` | sem expiração |
| **Meta** | `bikeflow_meta` | manifest, resultados de teste, health do pipeline | dbt `on-run-end` + jobs | sem expiração |

O que faz a separação ser real, e não três prefixos de nome:

- **As pastas do dbt não são as camadas.** `staging`/`intermediate`/`marts` é a organização idiomática do dbt *dentro* de silver e gold. Confundir os dois é a origem da bagunça do plano original → ADR-0006.
- **Bronze não é escrito pelo dbt.** É escrito por load job e pelo consumidor; o dbt só lê. Permite reprocessar silver/gold sem reingerir nada.
- **Batch e streaming convergem no silver**, não antes.
- **Contrato de promoção:** nada sobe de camada sem passar nos testes da camada (`quality_gate` entre `dbt build --select silver` e `--select gold`).
- Em GCP, cada camada vira um dataset com **IAM próprio** (bronze só para as SAs de pipeline; gold legível pelo BI).

---

## Modelagem corrigida

**Dimensões**
- `dim_station` — **SCD Tipo 2** a partir do GBFS `station_information` (nome, capacidade, lat/lon mudam). Chave natural: `station_id` (GBFS); chave de ligação com viagens: `short_name`.
- `dim_date`, `dim_time` — geradas, em `America/New_York`.
- `dim_member_type` (`member`/`casual`), `dim_rideable_type` (`classic_bike`/`electric_bike`).
- ~~`dim_bike`~~ — **removida** (sem fonte no schema atual).

**Fatos**
- `fct_trip` — grão: 1 viagem. PK `ride_id`. Partição `DATE(started_at_utc)`, cluster `start_station_key`. Métricas: `trip_duration_sec`, distância haversine.
- `fct_station_status` — grão: 1 estação × 1 observação distinta. Dedupe por (`station_id`, `last_reported`). Partição `DATE(observed_at_utc)`, cluster `station_id`.
- `fct_station_flow_hourly` — grão: estação × hora. `trips_out`, `trips_in`, `net_flow_trips`, `net_flow_observed`, **`unexplained_delta`** (= rebalanceamento inferido).

**Marts**
- `mart_station_status_current` — estado atual + status (`NORMAL`/`LOW_AVAILABILITY`/`CRITICAL_EMPTY`/`NEAR_CAPACITY`), com **thresholds parametrizados em `dbt_project.yml`**, não hardcoded.
- `mart_rebalancing_recommendation` — grão: estação × timestamp. **Materializada e historizada** (não view) — é isso que permite backtest.
- `mart_pipeline_health` — freshness, contagem de eventos, taxa de erro, resultados dos testes dbt.

**Fórmula da recomendação** (documentada, não mágica):
```
fill_ratio       = bikes_available / capacity
expected_demand  = média histórica de net_flow para (station, weekday, hour)   -- baseline
projected_ratio  = (bikes_available + expected_demand) / capacity
priority_score   = |projected_ratio - target_ratio| * capacity * peso_horário
action           = REDISTRIBUTE_BIKES | REMOVE_BIKES | NONE
```

---

## Qualidade de dados (concreto)

- **dbt tests:** `unique`/`not_null` em todas as PKs, `relationships` fato→dimensão, `accepted_values` em enums, `dbt_utils.expression_is_true` para `ended_at > started_at`, duração entre 1 min e 24 h, `0 <= bikes_available <= capacity`.
- **Freshness:** `dbt source freshness` — `warn_after: 15 min` / `error_after: 60 min` no streaming.
- **Reconciliação:** row count `bronze` vs `silver` por partição; taxa de match do `station_xref` com piso (falha se < 95%).
- **Quarentena:** linhas reprovadas vão para `_rejected` com o motivo, em vez de derrubar o pipeline.
- **Visibilidade:** resultados persistidos via `on-run-end` em `meta.dbt_test_results` e expostos na página *Engenharia* do dashboard.

### Lacunas de coleta viram feature, não desculpa

O poller GBFS roda na máquina local — ela não fica ligada 24/7. Em vez de esconder isso:
`fct_station_status` ganha `gap_minutes` (diferença para a observação anterior), os marts marcam
janelas com lacuna e os testes de freshness conhecem downtime planejado. Tratar coleta intermitente
como característica modelada e testada é exatamente o que se faz em produção.

---

## Fases (cada uma = 1 tag Git + 1 seção do README)

| Fase | Tag | Entrega |
|---|---|---|
| **0 — Fundação** | `v0.1-foundation` | `docker-compose.yml` (fake-gcs + Pub/Sub emulator), estrutura do repo, `pyproject.toml`, ruff + mypy + pytest, pre-commit, CI de lint/teste, `Makefile`, README esqueleto. **Airflow não entra aqui** — ver Fase 4 |
| **1 — Landing + Bronze** | `v0.2-batch-ingest` | Job de download (resolução de nome real, streaming p/ storage, `ingestion_manifest`, retry/backoff), normalização zip→Parquet em chunks, carga em `bronze.trips`, testes unitários com HTTP mockado |
| **2 — Silver + Gold** | `v0.3-dbt-marts` | dbt-core: silver (dedupe/UTC/`station_xref`/quarentena) e gold (SCD2, Kimball, marts), incremental por `MERGE`, todos os testes, macros de dialeto, `dbt docs` no GitHub Pages |
| **3 — Streaming** | `v0.4-streaming` | Poller GBFS (auto-discovery, CDC por `last_reported`, logging estruturado) → Pub/Sub emulator → consumidor → `bronze.station_status`; DLQ; agendado no Airflow a cada 2 min; silver/gold incrementais |
| **4 — Orquestração** | `v0.5-orchestration` | **Airflow entra aqui**, não antes — só faz sentido quando já existem jobs que se encadeiam e falham. DAGs: `resolve → fetch(landing) → validate → load_bronze → dbt build --select silver → quality_gate → dbt build --select gold → publish`; retries, SLA, alerta em falha |
| **5 — Observabilidade** | `v0.6-observability` | `meta.pipeline_health`, SLO de freshness documentado e medido, runbook de incidentes, alertas (falha de DAG, DLQ > 0, freshness estourada) |
| **6 — Dashboard + insight** | `v0.7-dashboard` | Evidence.dev: páginas Operacional / Analítico / Engenharia + `unexplained_delta` (rebalanceamento inferido) + backtest da recomendação; publicado no GitHub Pages |
| **7 — Validação BigQuery** | `v0.8-bq-dialect` | `profiles.yml` com target `sandbox`; job de CI opcional rodando o dbt no BigQuery Sandbox sobre 1 mês de amostra, provando portabilidade do SQL |
| **8 — ML (opcional)** | `v0.9-ml` | Baseline sazonal ingênuo **primeiro**; depois gradient boosting para net flow por estação/hora; clima via Open-Meteo (grátis, sem chave); split temporal; MAE vs baseline reportado **mesmo se o modelo perder** |
| **9 — Migração GCP (quando o billing destravar)** | `v1.0-gcp` | `terraform apply`, troca dos endpoints de emulador, Pub/Sub BigQuery Subscription no lugar do consumidor, Cloud Run Jobs, Looker Studio — com o **diff de código medido e publicado** ("migrar custou N linhas") |

A Fase 9 é o argumento mais forte do repositório: um diff pequeno prova que a arquitetura estava
desacoplada desde o início. Isso demonstra design melhor do que ter começado direto no GCP.

---

## Estrutura do repositório

```
bikeflow-data-engineer/
├── README.md                  ← o produto: problema → arquitetura → equivalência local/GCP → resultados → como rodar
├── Makefile                   ← up, demo, test, lint, docs, down
├── docker-compose.yml         ← fake-gcs-server, pubsub-emulator, airflow, evidence
├── docs/
│   ├── PLAN.md                ← este roadmap por fases
│   ├── architecture.md        ← diagramas mermaid (não ASCII)
│   ├── local-vs-gcp.md        ← tabela de equivalência + o que muda na migração
│   ├── data-dictionary.md
│   ├── runbook.md
│   ├── slo.md
│   └── adr/                   ← 0001-emuladores-vs-gcp-pago, 0002-dbt-vs-dataform,
│                                0003-airflow-local-vs-composer, 0004-chave-de-join-das-estacoes,
│                                0005-escopo-temporal-e-schema-legado,
│                                0006-medalhao-vs-pastas-dbt, 0007-duckdb-como-target-local
├── infra/terraform/           ← modules/{storage,bigquery,pubsub,cloudrun,monitoring,iam}, envs/{dev,prod}
│                                (validado no CI; apply pendente de billing — declarado no README)
├── ingestion/
│   ├── trips/                 ← resolver de nome, downloader, normalizador Parquet
│   ├── gbfs/                  ← poller com auto-discovery + CDC
│   └── common/                ← storage client (emulador ou GCS), manifest, logging, retry
├── streaming/consumer/        ← subscriber Pub/Sub → bronze
├── transform/dbt_bikeflow/    ← models/{staging,intermediate}→silver, models/marts→gold; macros/ (dialeto), tests/
├── orchestration/dags/        ← DAGs Airflow (idênticas às que rodariam no Composer)
├── dashboard/                 ← projeto Evidence.dev
├── tools/simulator/           ← gerador de carga (rotulado como teste, não como fonte)
├── tests/                     ← pytest (unit + integração contra os emuladores)
└── .github/workflows/         ← ci.yml (lint, pytest, dbt build em DuckDB, terraform validate),
                                 pages.yml (dbt docs + dashboard), bq-dialect.yml (opcional)
```

---

## Escopo de dados (decisão explícita)

- **Viagens:** 2024-01 até o mês completo mais recente (~19 meses, ~40 M viagens). Schema único pós-2021. `make demo` carrega **3 meses** para quem só quer clonar e rodar.
- **Schema legado (< 2021):** fora de escopo, com o motivo em ADR e o caminho de migração descrito. Declarar é melhor que ignorar.
- **Jersey City (`JC-`):** incluído — testa exatamente a fragilidade do resolver de nomes.
- **GBFS:** histórico construído pelo próprio pipeline a partir do go-live da Fase 3, com lacunas modeladas.
- **Licença:** nenhum dado bruto do Citi Bike versionado no Git; o dashboard público publica só agregados.

---

---

## Método de trabalho (modo guiado)

O objetivo declarado não é só ter o projeto pronto — é **aprender construindo**. Então cada etapa segue
sempre o mesmo ciclo:

1. **Por quê** — o problema que a etapa resolve e o que quebraria sem ela.
2. **O quê** — os arquivos que vão nascer e o papel de cada um.
3. **Mão na massa** — divisão híbrida:
   - **Eu escrevo:** boilerplate e infra — `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, CI, configs. Explicando as decisões, não só colando.
   - **Você escreve:** a lógica de negócio — parsers, transformações, models dbt, regras de qualidade. Eu passo a especificação e reviso o que você fizer.
4. **Checkpoint** — um comando concreto que prova que a etapa funcionou. Sem "deve funcionar": ou o comando passa, ou a etapa não acabou.
5. **Commit + tag** quando a fase fecha.

**Calibragem das explicações** (o usuário já tem Python, Docker e SQL/modelagem dimensional):
- **Rápido:** Python, Docker/compose, SQL, fato/dimensão.
- **Devagar e com contexto:** **dbt** (materializações, `ref()`, incremental, testes, o que ele *não* faz) e **Airflow** (DAG, operator, task, scheduling, idempotência, backfill) — são o terreno novo.
- **Sempre explicitado:** o *porquê* de cada decisão de arquitetura, porque é isso que você vai ter que defender numa entrevista.

### Ambiente já verificado nesta máquina

| Ferramenta | Status | Observação |
|---|---|---|
| Python 3.11.4 + pip | ✅ | suficiente |
| Docker 24.0.5 + Compose v2.20 | ✅ | suficiente |
| Git 2.41 | ✅ | |
| Node 22.19 | ✅ | usado só pelo Evidence.dev (Fase 6) |
| `gcloud` | ❌ | **não é bloqueio** — o emulador do Pub/Sub roda pela imagem Docker oficial |
| `terraform` | ❌ | só na Fase 1; pode rodar via Docker |

### Etapa 0 detalhada (a próxima a executar)

| Sub-etapa | O que faz e por quê | Quem escreve | Checkpoint |
|---|---|---|---|
| **0.1 — Esqueleto + higiene** | Estrutura de pastas, `.gitignore`, `pyproject.toml` (deps + config de ruff/mypy/pytest num só lugar), `Makefile`. Definir o contrato do projeto **antes** de escrever código evita refatoração de estrutura depois. | Eu | `pip install -e ".[dev]"` e `ruff check .` passam |
| **0.2 — Emuladores no compose** | `fake-gcs-server` + Pub/Sub emulator. Aqui explico **por que emulador e não mock**: mock testa o que você imaginou da API; emulador testa contra a API de verdade. É o que torna a migração para GCP um diff pequeno. | Eu | `docker compose up -d` e os dois respondem nas portas |
| **0.3 — "Hello, emulador"** | `ingestion/common/storage.py` e `messaging.py`: clientes que usam os SDKs **oficiais** do Google e trocam para o emulador só por variável de ambiente. É o coração da estratégia local-first — por isso **você** escreve. | **Você** (eu especifico e reviso) | Um script sobe arquivo no bucket e publica/consome 1 mensagem |
| **0.4 — Testes + CI** | pytest com fixtures que sobem os emuladores + GitHub Actions. Explico por que teste de ingestão se faz contra emulador, e por que CI desde o dia 1 e não no fim. | Eu | `make test` verde local e no push |

Nota sobre DuckDB: ele **não vira container**. É biblioteca embarcada — o "banco" é um arquivo `.duckdb`
no disco, como SQLite. Isso é diferente do modelo mental de Postgres/BigQuery e vale a pena registrar,
porque muda como você pensa backup, concorrência e CI.

---

## O que acontece logo após a aprovação

Não vou escrever toda a documentação de uma vez. **ADR se escreve no momento em que a decisão é
tomada** — escrever os sete agora seria ficção retroativa, que é exatamente o que os ADRs existem
para evitar. Cada fase produz o seu.

Ordem de execução imediata:

1. `plano.md` → movido para `docs/PLAN.md` com o conteúdo acima; `plano.md` removido.
2. Remover o diretório vazio `aa/`.
3. **Etapa 0.1** — `.gitignore`, estrutura de pastas, `pyproject.toml`, `Makefile`.
4. **Etapa 0.2** — `docker-compose.yml` com fake-gcs-server e Pub/Sub emulator.
5. **Etapa 0.3** — você escreve `storage.py` e `messaging.py`; eu especifico e reviso.
6. **Etapa 0.4** — pytest + GitHub Actions; `docs/adr/0001-emuladores-vs-gcp-pago.md`.
7. `README.md` mínimo + commit/tag `v0.1-foundation`.

Cada sub-etapa termina num checkpoint executável antes de eu seguir para a próxima.

## Verificação

- O documento não contém nenhuma das 8 falhas do bloco A (conferir linha a linha).
- Todos os endpoints citados respondem 200 (`gbfs.json`, `station_information.json`, `station_status.json`, índice do bucket `tripdata`).
- Os diagramas mermaid renderizam no preview do GitHub.
- O README responde, sem abrir outro arquivo: qual o problema de negócio, qual decisão a plataforma apoia, **como rodar sem conta GCP**, e o que muda quando houver GCP.
- Nenhum arquivo de dado bruto do Citi Bike versionado (restrição de licença).
