# BikeFlow — contexto do projeto

## O que é

Plataforma de dados para mobilidade compartilhada (Citi Bike NYC), construída
como projeto de portfólio de engenharia de dados. Pergunta de negócio: como
identificar desequilíbrios na distribuição de bicicletas e apoiar decisões de
redistribuição da frota.

**Leia `docs/PLAN.md` antes de qualquer coisa.** Ele tem a arquitetura, as
falhas já identificadas no plano original, o roadmap por fases e as decisões
tomadas com o porquê de cada uma.

## Como trabalhar com o Italo — IMPORTANTE

O objetivo declarado não é só entregar o projeto: é **aprender construindo**.
Modo híbrido acordado:

- **Claude escreve:** boilerplate e infra — `docker-compose.yml`, `Dockerfile`,
  `pyproject.toml`, CI, configs. Sempre explicando a decisão, nunca só colando.
- **Italo escreve:** a lógica de negócio — parsers, transformações, models dbt,
  regras de qualidade. Claude passa a especificação (assinatura + tipos +
  docstring + dicas nos pontos escorregadios) e **revisa depois**.

Ciclo de cada etapa: **por quê → o quê → mão na massa → checkpoint executável
→ commit**. Nunca "deve funcionar": ou o comando passa, ou a etapa não acabou.

Calibragem das explicações: ele já tem **Python, Docker e SQL/modelagem
dimensional**. Terreno novo é **dbt e Airflow** — explicar esses dois devagar
e com contexto. E sempre explicitar o *porquê* das decisões de arquitetura,
porque é isso que ele vai ter que defender numa entrevista.

## Onde estamos

**Fase 0 (Fundação), sub-etapa 0.3.**

- [x] **0.1** — esqueleto, `pyproject.toml`, `Makefile`, `.gitignore` — checkpoint verde
      (`ruff`, `ruff format`, `mypy` passaram)
- [x] **0.2** — `docker-compose.yml` com fake-gcs-server + Pub/Sub emulator — escrito e
      validado com `docker compose config`, mas **nunca testado de verdade** (o Docker
      Desktop do Windows estava quebrado). Falta o checkpoint: subir e ver os dois responderem.
- [ ] **0.3** — `src/bikeflow/common/storage.py` e `messaging.py` — **TAREFA DO ITALO**
- [ ] **0.4** — pytest com fixtures dos emuladores + GitHub Actions + `docs/adr/0001`

Os stubs da 0.3 estão com `raise NotImplementedError` e a especificação inteira
nas docstrings. **Não implemente por ele** — revise o que ele escrever.

Pendências abertas:
- Rodar `sudo service docker start` (pede senha, só o Italo pode).
- Fechar o checkpoint da 0.2.
- Commit + tag `v0.1-foundation` quando a Fase 0 terminar.

## Ambiente

- Projeto vive em `~/bikeflow-data-engineer` (ext4). **Nunca mover para
  `/mnt/c`**: medimos 48x mais lento para escrita de arquivo pequeno, que é
  exatamente o padrão de I/O de pip, pytest e dbt.
- Python 3.12.3; venv em `.venv/` — use `.venv/bin/python`.
- **Docker nativo do WSL, versão 27.4.1** (`/usr/bin/dockerd`). O Docker Desktop
  do Windows foi abandonado de propósito: `com.docker.service` estava parado, o
  proxy pipe↔VM devolvia 500/Bad Gateway, e a versão era 24.0.5 (2023).
- **Sem systemd no WSL** (PID 1 é `init`). O daemon sobe com
  `sudo service docker start`, não com `systemctl`.
- O usuário já está no grupo `docker` — não precisa de sudo para usar o cliente.

## Git

- Remote: `git@github.com:AndradeItalo/bikeflow-data-engineer.git` — **SSH**, autenticado
  pela chave `~/.ssh/id_ed25519`. Foi trocado de HTTPS para SSH porque não havia
  credential helper e o push pediria PAT toda vez.
- `user.email` **local deste repo** é `102003839+AndradeItalo@users.noreply.github.com`,
  não o gmail do config global. Dois motivos: casa com o commit inicial (o GitHub
  atribui commit à conta pelo email, e email divergente = commit sem link para o
  perfil) e mantém o email pessoal fora de um repo público.
- Branch: `main`.

## Convenções

- **Camadas:** landing → bronze → silver → gold (+ meta). As pastas do dbt
  (`staging`/`intermediate`/`marts`) **não são** as camadas — são a organização
  interna do dbt dentro de silver e gold. Ver `docs/PLAN.md`.
- **Nenhum dado bruto do Citi Bike entra no Git** — a licença proíbe
  redistribuir como dataset standalone.
- **ADR se escreve quando a decisão é tomada**, nunca retroativamente.
- Commit + tag ao fechar cada fase (`v0.1-foundation`, `v0.2-batch-ingest`, ...).
- Fim de linha LF sempre, garantido por `.gitattributes`.
- Emulador em vez de mock: mock testa o que você imaginou da API; emulador testa
  contra uma implementação real do contrato.
