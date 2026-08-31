# Imagem oficial do Airflow + o pacote bikeflow instalado dentro dela.
#
# Por que instalar o pacote na imagem em vez de so' montar src/ como volume:
# LocalExecutor roda as tasks como subprocesso local do proprio container do
# scheduler - "import bikeflow" dentro da task precisa achar o pacote e suas
# dependencias (google-cloud-storage, pyarrow, duckdb, dbt) instaladas ali.
#
# Risco conhecido: Airflow fixa versoes de dependencias com rigor (o arquivo
# de constraints oficial). Instalar nosso pacote por cima pode conflitar -
# validado empiricamente no build, nao assumido.
FROM apache/airflow:2.10.5-python3.12

# --chown=airflow:root: a imagem base roda como usuario nao-root 'airflow'.
# Sem isso, o COPY cria os arquivos como root e o 'pip install -e' falha
# tentando escrever src/bikeflow.egg-info (sem permissao) - erro real visto
# no build, nao suposicao.
COPY --chown=airflow:root pyproject.toml README.md /opt/bikeflow/
COPY --chown=airflow:root src/ /opt/bikeflow/src/
RUN pip install --no-cache-dir -e "/opt/bikeflow[dbt]"
