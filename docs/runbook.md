# Runbook — incidentes do pipeline

Cobre só os alertas que **existem de verdade** no projeto hoje (Fases 4.4 e
5.5). Nada especulativo — cada seção diz exatamente que task falha, onde o
e-mail aparece e quais comandos rodar pra confirmar/corrigir.

## Onde o alerta aparece

Toda falha de task (`email_on_failure=True`, as duas DAGs) manda e-mail via
Mailpit — SMTP de teste local, não um serviço de e-mail de verdade.

**UI do Mailpit**: http://localhost:8025 (só com `make airflow-up` de pé).

**UI do Airflow**: http://localhost:8080 (admin/admin) — `Graph`/`Logs` da
run que falhou é sempre o primeiro lugar pra olhar, o e-mail só avisa que
algo quebrou, não diz o quê.

Sem deduplicação: um problema persistente na `station_status_streaming`
(agendada a cada 2 min) reenvia e-mail a cada ciclo até ser resolvido.
Muitos e-mails iguais seguidos = mesmo incidente, não N incidentes.

---

## 1. Falha genérica de task (qualquer DAG)

**Sintoma**: e-mail do Mailpit com o nome da task que falhou. Antes de mais
nada, abrir o log da task no Airflow — a exceção real está lá.

**Causas mais comuns já vistas neste projeto** (ver `docs/findings-log.md`
para o histórico completo):
- Docker/emuladores fora do ar (`docker ps` — `bikeflow-gcs`/`bikeflow-pubsub`
  saudáveis?).
- `.env`/bucket ausentes numa base nova (checar `make seed-bronze` já rodou).
- Permissão do `data/bikeflow.duckdb` (bind mount, uid do container ≠ uid do
  host) — sintoma: `Permission denied` no log. Corrigir com `chmod 666
  data/bikeflow.duckdb && chmod 777 data` (mesmo passo do `make airflow-up`).

**Verificação de que resolveu**: re-rodar a task pela UI do Airflow
(`Clear` → aguarda o retry automático ou dispara manual) e confirmar `success`
no Graph.

---

## 2. DLQ > 0 (`check_dlq`, DAG `station_status_streaming`)

**Sintoma**: e-mail com o assunto da task `check_dlq`. O corpo/log traz a
lista de mensagens (`RuntimeError: N mensagem(ns) na DLQ: [...]`) — o próprio
payload que falhou está ali, não precisa investigar às cegas.

**O que já sabemos que causa isso**: campo obrigatório faltando no payload
do GBFS (`station_id`/`last_reported`) depois de esgotar as 5 tentativas de
redelivery. Ver `docstring` de `consumer.py` pro mecanismo completo.

**Diagnóstico**:
```bash
.venv/bin/python -c "
from bikeflow.common import messaging
print(messaging.peek_dlq())
"
```
`peek_dlq()` **não consome** (nacka de volta) — rodar isso não faz a
mensagem sumir, dá pra chamar quantas vezes precisar enquanto investiga.

**Resolução**:
- Se for payload realmente malformado (bug upstream do GBFS, formato mudou):
  documentar em `docs/findings-log.md` e decidir se `consumer.py` precisa de
  um caso novo de validação.
- Depois de entender/corrigir a causa, **drenar a DLQ de verdade** (peek não
  limpa):
  ```bash
  .venv/bin/python -c "
  from bikeflow.common import messaging
  print(messaging.pull_once(max_messages=50, subscription_id='station-status-dlq-sub', timeout=5))
  "
  ```
  Isso dá `ack` nas mensagens puxadas — só rodar depois de já ter guardado o
  payload (do `peek_dlq()` acima) se for querer investigar depois.

**Verificação de que resolveu**: `peek_dlq()` volta `[]` e o próximo ciclo
da DAG (até 2 min) não gera novo e-mail.

---

## 3. Freshness estourada (`check_freshness`, DAG `station_status_streaming`)

**Sintoma**: e-mail da task `check_freshness`. Log mostra `ERROR STALE
freshness of bronze.station_status` — `bronze.station_status` não recebeu
linha nova há mais de 60 min (limite configurado em `_sources.yml`, Fase
5.2; SLO alvo é bem mais apertado, ver `docs/slo.md`).

**Diagnóstico**:
```bash
make dbt-freshness
```
ou direto:
```sql
select max(_ingested_at), now() from bronze.station_status;
```

**Causas mais prováveis**:
- `poll`/`consume` da mesma DAG já estavam falhando antes (checar o Graph —
  se `poll`/`consume` estão vermelhos, a causa raiz está lá, não aqui).
- GBFS externo fora do ar ou mudou de formato (`client.py` faz
  auto-discovery — testar `poll_once()` isolado pra confirmar se o feed
  responde).
- Scheduler do Airflow parado/atrasado (checar `airflow-scheduler` nos
  logs: `make airflow-logs`).

**Verificação de que resolveu**: `make dbt-freshness` volta `PASS`.

---

## Painel de diagnóstico: `mart_pipeline_health`

Antes de investigar qualquer alerta acima, vale olhar
`gold.mart_pipeline_health` (Fase 5.4) — 1 linha, snapshot da saúde como um
todo (freshness p95/max, volume, taxa de erro dos testes dbt da invocação
anterior):
```sql
select * from gold.mart_pipeline_health;
```
Lembrete importante (documentado no próprio model): os campos de teste
(`tests_*`) refletem a invocação **anterior** do dbt, nunca a atual — é
esperado, não é dado desatualizado por engano.
