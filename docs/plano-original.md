Por que esse projeto seria diferente?

Mesmo sendo mobilidade, o problema muda completamente.

Com táxis, você provavelmente trabalhou com:

demanda → viagens → distância → faturamento.

Com bicicletas compartilhadas, você pode trabalhar com operação e distribuição da frota:

Onde estão as bicicletas?
Quais estações ficam vazias com frequência?
Quais acumulam bicicletas?
Como prever a necessidade de redistribuição?

Isso cria um problema de negócio bem mais interessante.

Projeto: BikeFlow — Plataforma de Dados para Mobilidade Compartilhada
Cenário

Uma empresa de bicicletas compartilhadas possui centenas de estações.

Ao longo do dia:

Usuários retiram bicicletas
Usuários devolvem bicicletas
Algumas estações ficam vazias
Outras ficam lotadas
A empresa precisa redistribuir bicicletas

O objetivo da plataforma seria responder:

Como usar dados para identificar desequilíbrios na distribuição de bicicletas e apoiar decisões de redistribuição da frota?

Arquitetura sugerida
                  DADOS HISTÓRICOS
                       │
                       ▼
              Python Ingestion
                       │
                       ▼
                Cloud Storage
                   RAW / BRONZE
                       │
                       ▼
                  BigQuery RAW
                       │
                       ▼
                 Dataform / dbt
                       │
                       ▼
             BigQuery SILVER / GOLD
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Analytics         Machine Learning
              │                 │
              └────────┬────────┘
                       ▼
                 Looker Dashboard

E o fluxo em tempo real:

Bike/Event Simulator
         │
         ▼
       Pub/Sub
         │
         ▼
       Dataflow
         │
         ▼
       BigQuery
         │
         ▼
Real-Time Monitoring
Stack que eu usaria
Etapa	Tecnologia
Ingestão Batch	Python
Streaming	Pub/Sub
Processamento Streaming	Dataflow
Data Lake	Cloud Storage
Data Warehouse	BigQuery
Transformação	Dataform
Orquestração	Cloud Composer
Machine Learning	BigQuery ML
Dashboard	Looker Studio
Infraestrutura	Terraform
CI/CD	GitHub Actions
Monitoramento	Cloud Monitoring
O que deixaria o projeto realmente interessante

Eu dividiria em Batch + Streaming.

1. Pipeline Batch

Os arquivos históricos entram periodicamente:

Citi Bike Data
      ↓
Python Downloader
      ↓
Cloud Storage
      ↓
BigQuery RAW
      ↓
Dataform
      ↓
BigQuery Trusted
      ↓
BigQuery Analytics
      ↓
Dashboard

Aqui você demonstra:

Ingestão incremental
Arquivos Parquet
Particionamento
Clustering
Idempotência
Deduplicação
Data Quality
Modelagem dimensional
2. Pipeline Streaming

Você cria eventos simulando o uso das bicicletas:

{
  "event_id": "evt_123",
  "bike_id": "bike_456",
  "station_id": "station_789",
  "event_type": "bike_rented",
  "event_timestamp": "2026-08-14T22:30:00Z"
}

Outro evento:

{
  "event_id": "evt_124",
  "bike_id": "bike_456",
  "station_id": "station_222",
  "event_type": "bike_returned",
  "event_timestamp": "2026-08-14T22:47:00Z"
}

Fluxo:

Python Simulator
       ↓
    Pub/Sub
       ↓
    Dataflow
       ↓
    BigQuery
       ↓
Monitoring Dashboard
KPIs
Operacionais
Total de bicicletas ativas
Viagens por hora
Duração média da viagem
Estações mais utilizadas
Estações com maior saída
Estações com maior entrada
Taxa de ocupação estimada
Estações potencialmente vazias
Estações potencialmente lotadas
Analytics
Horários de pico
Rotas mais frequentes
Dias com maior utilização
Uso por tipo de usuário
Uso por tipo de bicicleta
Crescimento de viagens
Engenharia
Eventos processados por minuto
Latência do pipeline
Eventos inválidos
Eventos duplicados
Data freshness
Falhas por pipeline
Modelagem
dim_bike
dim_station
dim_date
dim_time
dim_user_type
        │
        ▼
     fact_trip
        │
        ├── trip_duration
        ├── start_station
        ├── end_station
        └── bike_type

Para streaming:

fact_bike_event

Com:

event_id
bike_id
station_id
event_type
event_timestamp
processed_timestamp

Depois, você cria uma tabela analítica:

mart_station_status

Exemplo:

station_id
station_name
estimated_bikes_available
estimated_empty_slots
last_event_timestamp
station_status

Onde station_status poderia ser:

NORMAL
LOW_AVAILABILITY
CRITICAL_EMPTY
NEAR_CAPACITY
O diferencial do projeto

Aqui está a parte que eu acho mais forte:

Você não precisa apenas analisar o passado.

Você pode criar uma lógica para responder:

Qual estação precisa receber ou remover bicicletas?

Por exemplo:

Estação A
Capacidade: 40
Bicicletas estimadas: 3


Status: CRITICAL_EMPTY
Ação: REDISTRIBUTE_BIKES

E:

Estação B
Capacidade: 40
Bicicletas estimadas: 38


Status: NEAR_CAPACITY
Ação: REMOVE_BIKES

Você estaria construindo uma plataforma de decisão operacional, e não apenas um dashboard.

Como eu faria em etapas
Fase 1 — MVP
Citi Bike Data
      ↓
Python
      ↓
Cloud Storage
      ↓
BigQuery
      ↓
Dashboard
Fase 2 — Engenharia

Adicionar:

Raw / Trusted / Gold
Dataform
Incremental load
MERGE
Particionamento
Clustering
Testes de qualidade
Fase 3 — Orquestração

Adicionar:

Cloud Composer


download
   ↓
validate
   ↓
load_raw
   ↓
transform
   ↓
quality_check
   ↓
build_marts
Fase 4 — Streaming
Event Simulator
      ↓
Pub/Sub
      ↓
Dataflow
      ↓
BigQuery
Fase 5 — Machine Learning

Aqui você poderia usar BigQuery ML para tentar prever:

Quantas bicicletas uma estação precisará nas próximas horas?

Por exemplo:

station_id
hour
day_of_week
historical_rides
weather
       ↓
       ML Model
       ↓
Predicted demand

Isso seria um diferencial muito interessante porque o ML teria uma aplicação clara dentro do problema de negócio.



E o mais interessante é que você pode consumir dois tipos de dados diferentes da Citi Bike:

Histórico de viagens → Batch
Status atual das estações → Real-time

Isso deixa o projeto muito mais interessante porque você não precisa inventar o streaming.

1. Dados históricos: baixar os arquivos mensais

A própria Citi Bike System Data disponibiliza os históricos das viagens para download. Os arquivos incluem campos como ride_id, tipo da bicicleta, início e fim da viagem, estações de origem/destino, coordenadas e tipo de usuário.

Os arquivos ficam em um bucket público e seguem um padrão de nome como:

202601-citibike-tripdata.zip
202602-citibike-tripdata.zip
202603-citibike-tripdata.zip

Por exemplo, o índice público mostra arquivos mensais até junho de 2026, embora o tamanho dos arquivos varie bastante.

Como consumir?

Você pode criar um script Python que recebe ano e mês e monta a URL:

import requests


year = 2026
month = 6


url = (
    f"https://s3.amazonaws.com/tripdata/"
    f"{year}{month:02d}-citibike-tripdata.zip"
)


response = requests.get(url)
response.raise_for_status()


with open(f"{year}{month:02d}-citibike-tripdata.zip", "wb") as file:
    file.write(response.content)


print("Download concluído!")

Mas eu não faria o download para sua máquina no projeto final.

Faria direto:

Citi Bike
   ↓
Python Ingestion
   ↓
Google Cloud Storage

Ou seja, seu pipeline baixa o arquivo e envia para o bucket.

Estrutura do bucket
gs://movedata-datalake/
│
└── raw/
    └── citibike/
        └── trips/
            ├── year=2026/
            │   ├── month=01/
            │   │   └── tripdata.zip
            │   ├── month=02/
            │   │   └── tripdata.zip
            │   └── month=03/
            │       └── tripdata.zip
Pipeline
Cloud Composer
      │
      ▼
Python Ingestion
      │
      ├── Monta URL do mês
      │
      ├── Baixa arquivo
      │
      ├── Valida arquivo
      │
      ▼
Cloud Storage RAW
      │
      ▼
BigQuery
2. Dados em tempo real: aqui está o grande diferencial

A Citi Bike também publica dados em tempo real usando GBFS — General Bikeshare Feed Specification. GBFS é justamente uma especificação para expor o status atual de sistemas de mobilidade compartilhada por meio de feeds JSON.

Um dos endpoints disponibilizados é o feed de status das estações:

Citi Bike Live Station Feed

O feed fornece o estado atual das estações, como quantidade de bicicletas e vagas disponíveis. A especificação GBFS define station_status como um feed de disponibilidade das estações.

Você pode consumir diretamente com Python
import requests


url = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"


response = requests.get(url)
response.raise_for_status()


data = response.json()


stations = data["data"]["stations"]


for station in stations[:5]:
    print({
        "station_id": station["station_id"],
        "num_bikes_available": station["num_bikes_available"],
        "num_docks_available": station["num_docks_available"]
    })

Então você recebe algo conceitualmente assim:

{
    "station_id": "123",
    "num_bikes_available": 12,
    "num_docks_available": 8,
    "is_installed": 1,
    "is_renting": 1,
    "last_reported": 1780000000
}
E como isso vira um projeto de streaming?

Aqui está o ponto mais interessante: você cria um processo que consulta essa API periodicamente.

Por exemplo:

A cada 1 minuto
       │
       ▼
Consulta GBFS API
       │
       ▼
Recebe status atual
       │
       ▼
Publica eventos no Pub/Sub
       │
       ▼
Dataflow
       │
       ▼
BigQuery
Arquitetura
                  ┌──────────────────────┐
                  │ Citi Bike GBFS API   │
                  │ station_status.json  │
                  └──────────┬───────────┘
                             │
                     Python Consumer
                             │
                             ▼
                         Pub/Sub
                             │
                             ▼
                         Dataflow
                             │
                             ▼
                     BigQuery RAW
                             │
                             ▼
                    BigQuery Analytics
                             │
                             ▼
                      Looker Dashboard
Exemplo do producer

Seu código poderia funcionar assim:

import json
import requests
from google.cloud import pubsub_v1


PROJECT_ID = "seu-projeto"
TOPIC_ID = "bike-station-events"


publisher = pubsub_v1.PublisherClient()


topic_path = publisher.topic_path(
    PROJECT_ID,
    TOPIC_ID
)


url = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"


response = requests.get(url)
stations = response.json()["data"]["stations"]


for station in stations:
    
    message = {
        "station_id": station["station_id"],
        "bikes_available": station["num_bikes_available"],
        "docks_available": station["num_docks_available"],
        "last_reported": station["last_reported"]
    }


    publisher.publish(
        topic_path,
        json.dumps(message).encode("utf-8")
    )


print("Eventos publicados!")
O fluxo seria:
API retorna:


Station A → 10 bikes
Station B → 2 bikes
Station C → 18 bikes


        ↓


Seu consumer transforma cada registro
em um evento


        ↓


Pub/Sub


        ↓


Dataflow processa


        ↓


BigQuery armazena o histórico

Na próxima consulta:

Station A → 8 bikes
Station B → 0 bikes
Station C → 20 bikes

Você consegue acompanhar a evolução do estado das estações ao longo do tempo.

E como pegar os dados das estações?

Além de station_status, a estrutura GBFS possui feeds para informações estáticas das estações, incluindo capacidade e localização. A especificação define station_information para listar estações, suas capacidades e localizações, enquanto station_status representa disponibilidade.

Então eu teria dois pipelines:

Pipeline 1 — Informações das estações
GBFS station_information
         ↓
Cloud Storage
         ↓
BigQuery dim_station

Dados como:

station_id
name
lat
lon
capacity

Esse dado não muda tanto.

Pipeline 2 — Status em tempo real
GBFS station_status
         ↓
Python Consumer
         ↓
Pub/Sub
         ↓
Dataflow
         ↓
fact_station_status

Dados como:

station_id
bikes_available
docks_available
observed_at
ingested_at
Aqui está uma arquitetura muito boa para seu projeto
                         BATCH
                           
          Citi Bike Trip History Files
                    │
                    ▼
             Python Downloader
                    │
                    ▼
          Cloud Storage / RAW
                    │
                    ▼
              BigQuery Bronze
                    │
                    ▼
                 Dataform
                    │
                    ▼
          BigQuery Silver / Gold
                    │
                    ▼
                  Looker




                    REAL-TIME


             Citi Bike GBFS API
                    │
                    ▼
             Python Consumer
                    │
                    ▼
                 Pub/Sub
                    │
                    ▼
                 Dataflow
                    │
                    ▼
             BigQuery Streaming
                    │
                    ▼
             Real-Time Dashboard
O que eu faria na prática

Eu começaria sem complicar demais:

Etapa 1

Consumir o histórico:

Citi Bike → Python → GCS
Etapa 2
GCS → BigQuery RAW → Dataform → Gold
Etapa 3

Consumir a API real:

GBFS API → Python

Primeiro você testa localmente.

Etapa 4

Transformar o consumer em um processo contínuo:

GBFS API → Python → Pub/Sub
Etapa 5
Pub/Sub → Dataflow → BigQuery
Etapa 6

Cruzar o histórico de viagens com o histórico de disponibilidade das estações que você mesmo coletou.

Esse último ponto é, para mim, o grande diferencial: o GBFS é em tempo real e não é pensado para fornecer histórico, então seu pipeline passa a ser responsável por capturar snapshots periódicos e construir esse histórico operacional.