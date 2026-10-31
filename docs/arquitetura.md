# Arquitetura

```
src/f1/
├── cli.py                 # f1-extract: argparse -> extract() -> pipeline.run
├── pipeline.py            # extract -> transform -> load; RunSummary
├── exceptions.py          # F1Error, OpenF1APIError, InvalidRecordError, WriteError
├── config/settings.py     # Settings (pydantic-settings, prefixo F1_)
├── clients/openf1.py      # OpenF1Client: retry/backoff, intervalo mínimo, 404 -> []
├── extract/               # registro de endpoints e funções fetch_*
├── transform/normalize.py # datas, metadados, dedupe e tipos mistos (funções puras)
├── load/                  # Partition, Protocol Writer e LocalWriter (JSON/Parquet)
├── dashboard/
│   ├── data.py            # leitura do cache (sem Streamlit)
│   ├── charts.py          # tabelas e figuras Plotly (funções puras)
│   ├── app.py             # Streamlit: só layout e orquestração
│   └── __main__.py        # f1-dashboard: streamlit run app.py
└── utils/logging.py
```

## Fluxo de dados

```
OpenF1 API ──> OpenF1Client ──> extract ──> normalize ──> LocalWriter ──> data/
                                                                           │
                         dashboard/app.py <── charts <── dashboard/data ◄──┘
```

1. O extrator (CLI ou botões do dashboard) chama `cli.extract`, que monta o
   `OpenF1Client` e o `LocalWriter` a partir das `Settings` e executa `pipeline.run`.
2. `meetings` e `sessions` são buscados por `?year=`. Os endpoints por sessão usam
   `?session_key=` e o `weather` usa `?meeting_key=`.
3. Cada partição é normalizada e gravada em `raw/` (JSON) e `processed/` (Parquet).
   Falhas são contadas no `RunSummary`, sem interromper as demais partições.
4. O dashboard lê só o Parquet. Os loaders usam `st.cache_data` com o mtime mais
   recente do cache na chave, então um download novo aparece sem reiniciar o app.

## Endpoints

| Endpoint | Escopo | Chave primária (dedupe) | Visão |
|---|---|---|---|
| meetings | year | meeting_key | filtro de GP |
| sessions | year | session_key | filtro de sessão |
| drivers | session | session_key, driver_number | nomes e cores |
| laps | session | session_key, driver_number, lap_number | Ritmo |
| session_result | session | session_key, driver_number | Resultado |
| pit | session | session_key, driver_number, lap_number | Pneus |
| stints | session | session_key, driver_number, stint_number | Pneus |
| weather | meeting | meeting_key, date | Clima |

Ficam de fora `car_data` e `location` (telemetria de alto volume), além de `intervals`,
`position`, `overtakes`, `race_control`, `team_radio`, `championship_*` e `starting_grid`.

## Partições e idempotência

```
data/raw/<endpoint>/year=YYYY/[meeting_key=M/][session_key=S/]data.json
data/processed/<endpoint>/year=YYYY/[meeting_key=M/][session_key=S/]data.parquet
```

- As partições são determinísticas: reprocessar sobrescreve o arquivo inteiro.
- A escrita é atômica: grava em `data.*.tmp` e depois faz `Path.replace()`.
- Respostas vazias (ou 404) não geram arquivo.

## Particularidades dos dados

- `gap_to_leader` vem como número, texto (`"+1 LAP"`) ou lista (Q1/Q2/Q3 na
  classificação). A normalização converte misturas em texto e o dashboard formata
  todos os casos.
- A duração do pit muda de coluna conforme a temporada (`stop_duration`,
  `pit_duration`, `lane_duration`). O dashboard usa a primeira que não for nula.
- O `weather` é por meeting. O dashboard filtra por `session_key` (ou, sem essa
  coluna, pela janela de horário da sessão).

## Desvios do padrão do time

| Padrão | Neste projeto | Motivo |
|---|---|---|
| `handler.py` de Lambda | `cli.py` + `dashboard/app.py`, que só orquestram | Execução local |
| boto3 / moto / S3 | Não usados | Cache local; testes de I/O com `tmp_path` |
| Segredos no Secrets Manager/SSM | Não há segredos | Dados históricos abertos |
| `poetry export` para Lambda | Não aplicável | Sem empacotamento para Lambda |

A camada `load/` fica atrás do protocolo `Writer`: um writer de S3 pode entrar sem
mexer no restante.
