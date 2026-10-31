# Plano — Dashboard OpenF1 (`f1`)

## Contexto

Projeto de aula: um projeto Python que consome a API pública OpenF1 (ver `.claude/doc_api.md`) e apresenta os dados em um **dashboard interativo**. O `plan.md` anterior cobria só a extração (ETL para JSON/Parquet), porque o pedido de dashboard não chegou à sessão que o gerou e o `SKILL.md` puxa para extratores. Este plano mantém um extrator enxuto como camada de dados e acrescenta o dashboard, que é o objetivo real.

Todo o código segue o `.claude/SKILL.md` (Poetry 2.x, layout `src/`, Ruff, pytest com cobertura ≥ 50%, mypy strict, mkdocs-material, docstrings Google, logging, idempotência).

Estado atual: o repositório está no `first commit`. Há `pyproject.toml` do `poetry new` (`requires-python = ">=3.15"`, autor placeholder), `src/f1/__init__.py` e `tests/__init__.py` vazios, `.python-version` = `3.12.10` e Poetry 2.5.1.

### Decisões (confirmadas com o usuário)
- **Dashboard:** Streamlit + Plotly, app local. Filtros de ano, GP, sessão e pilotos na barra lateral.
- **Dados:** extração para cache local em Parquet (`data/processed/`, e JSON bruto em `data/raw/`). O dashboard lê só o Parquet (rápido, funciona offline, respeita o rate limit). Um botão no dashboard baixa uma sessão que ainda não esteja no cache.
- **Visões:** resultado da sessão, ritmo por volta, estratégia de pneus (com pit stops) e clima da pista.
- **Endpoints:** `meetings`, `sessions`, `drivers`, `laps`, `session_result`, `pit`, `stints` e `weather`. Ficam de fora: `car_data`/`location` (telemetria de alto volume) e os demais.
- **Comandos:** `poetry run task <lint|format|test|docs|extract|dashboard>` (taskipy), além do `Makefile` do SKILL.

### Desvios do SKILL.md (avisados de forma explícita)
| Regra do SKILL | Neste projeto | Motivo |
|---|---|---|
| `handler.py` de Lambda | `cli.py` (extração) + `dashboard/app.py` (UI), que só orquestram | Execução local, sem Lambda |
| boto3 / moto / S3 | Não usados | Destino local; testes de I/O com `tmp_path` |
| Segredos no Secrets Manager/SSM | Não há segredos | Dados históricos da OpenF1 são abertos |
| `poetry export` | Não aplicável | Sem empacotamento para Lambda |

## Arquitetura

```
src/f1/
├── cli.py                 # f1-extract: argparse -> pipeline.run
├── pipeline.py            # extract -> transform -> load; RunSummary
├── exceptions.py          # F1Error, OpenF1APIError, InvalidRecordError, WriteError
├── config/settings.py     # Settings (pydantic-settings, prefixo F1_), get_settings() com lru_cache
├── clients/openf1.py      # OpenF1Client (retry/backoff em 429/5xx/timeout, min_interval, 404 -> [])
├── extract/endpoints.py   # EndpointSpec(name, scope, primary_keys), registro imutável
├── extract/openf1.py      # fetch_meetings/sessions/by_session/by_meeting
├── transform/normalize.py # parse_dates, add_metadata, deduplicate, coerce_mixed_types, normalize
├── load/base.py           # Partition (year/meeting_key/session_key) + Protocol Writer
├── load/local.py          # LocalWriter: JSON + Parquet, escrita atômica (.tmp + replace)
├── dashboard/
│   ├── data.py            # leitura do cache: catálogo e DataFrames de uma sessão
│   ├── charts.py          # funções puras DataFrame -> plotly Figure
│   └── app.py             # Streamlit: só layout e orquestração
└── utils/logging.py       # setup_logging(level)
```

### Camada de dados (extrator)
Reaproveita o desenho do plano anterior, que já foi validado contra a API real (corrida 9472, Bahrein 2024: 1.755 linhas sem falhas, idempotente):
- Partições `data/{raw,processed}/<endpoint>/year=YYYY/[meeting_key=M/][session_key=S/]data.{json,parquet}`. Reprocessar sobrescreve a partição.
- Escopos: `meetings` e `sessions` por ano (sempre gravados com o ano inteiro); `weather` por `meeting_key`; os demais por `session_key`.
- Lições da execução real:
  - `coerce_mixed_types`: `gap_to_leader` vem como número ou `"+1 LAP"`; mistura de `int` e `float` vira `float`, qualquer outra mistura vira texto.
  - Montar a tabela Arrow com a **união** das colunas, porque `pa.Table.from_pylist` descarta colunas ausentes no primeiro registro.
- CLI: `f1-extract --year 2024 [--endpoints ...] [--session-key N] [--log-level]`. Código de saída 1 se alguma partição falhar.

### Dashboard (`dashboard/`)
**`data.py`** (sem Streamlit, testável com `tmp_path`):
- `available_years(data_dir)`, `load_meetings(data_dir, year)` e `load_sessions(data_dir, year)`, que leem as partições de ano.
- `session_cached(data_dir, partition) -> bool`, que diz se `laps`/`session_result`/`stints` existem.
- `load_session_data(data_dir, year, meeting_key, session_key) -> SessionData` (dataclass com DataFrames `drivers`, `results`, `laps`, `stints`, `pit` e `weather`). Endpoint ausente vira DataFrame vazio.
- O `weather` é filtrado pela janela `date_start`/`date_end` da sessão.
- Leitura com `pandas.read_parquet` (pyarrow).

**`charts.py`** (funções puras, retornam `plotly.graph_objects.Figure` ou DataFrame):
- `results_table(results, drivers)`: posição, piloto (sigla), equipe, voltas, gap e status (DNF/DNS/DSQ). Trata `gap_to_leader` como texto ou lista (classificação).
- `lap_pace(laps, drivers, drivers_sel, exclude_outliers)`: linha volta × `lap_duration` por piloto, com a cor da equipe (`team_colour`). O filtro opcional remove voltas de saída do box (`is_pit_out_lap`) e voltas acima de 107% da mediana.
- `tyre_strategy(stints, pit, drivers)`: Gantt horizontal `lap_start` → `lap_end` por piloto, colorido pelo composto (SOFT vermelho, MEDIUM amarelo, HARD cinza, INTERMEDIATE verde, WET azul), com marcadores de pit stop e `stop_duration` no hover.
- `weather_chart(weather)`: temperatura do ar e da pista ao longo do tempo (eixo secundário para umidade) e faixas de chuva (`rainfall`).
- Entrada vazia vira uma figura com a anotação "Sem dados".

**`app.py`** (Streamlit, só orquestra):
- Barra lateral: ano → GP (`meeting_name`) → sessão (`session_name`) → pilotos (multiselect, todos por padrão).
- Se o calendário do ano não estiver em cache: botão "Baixar calendário", que chama `pipeline.run(endpoints=meetings,sessions)`.
- Se a sessão não estiver em cache: botão "Baixar dados da sessão", que chama `pipeline.run(..., session_key=...)` com `st.spinner`. Falhas do `RunSummary` aparecem em `st.error`.
- Abas: Resultado | Ritmo | Pneus | Clima. Os loaders usam `@st.cache_data`, cuja chave inclui o mtime dos arquivos.
- Entrypoint `f1-dashboard` (em `dashboard/__main__.py` ou `cli.py`), que executa `streamlit run` no `app.py` usando `streamlit.web.cli`.

## Dependências

```bash
poetry add requests pydantic-settings pyarrow pandas streamlit plotly
poetry add --group dev ruff pytest pytest-cov pytest-mock mypy pre-commit taskipy types-requests pyarrow-stubs pandas-stubs
poetry add --group docs mkdocs-material "mkdocstrings[python]"
```

Tasks no `pyproject.toml` (`[tool.taskipy.tasks]`): `lint`, `format`, `test`, `docs`, `extract` (`f1-extract`) e `dashboard` (`f1-dashboard`). Mypy: `ignore_missing_imports` só para `plotly.*` e `streamlit.*`, se faltarem stubs (avisar).

## Fases (um commit por fase, Conventional Commits)

0. `chore: configura tooling do projeto`: `pyproject.toml` (`requires-python = ">=3.12,<3.13"`, autor, scripts `f1-extract`/`f1-dashboard`, blocos ruff/pytest/coverage/mypy da seção 7 do SKILL, taskipy), `poetry.toml` (venv no projeto), `.gitignore` (+ `data/`), `.pre-commit-config.yaml` (ruff rev igual ao da venv), `Makefile` e a árvore `src/` e `tests/unit/` espelhada.
1. `feat: settings, logging e exceções` + testes.
2. `feat: cliente HTTP da OpenF1` + testes (mock de `Session.get`, `time.sleep`/`monotonic`).
3. `feat: extração dos endpoints` + testes com `FakeClient` em `tests/conftest.py`.
4. `feat: normalização e dedupe` + testes parametrizados (inclui tipos mistos).
5. `feat: writer local JSON/Parquet idempotente` + testes com `tmp_path`.
6. `feat: pipeline e CLI f1-extract` + testes.
7. `feat: leitura do cache para o dashboard` (`dashboard/data.py`) + testes com Parquet gerado pelo `LocalWriter` em `tmp_path`.
8. `feat: gráficos do dashboard` (`dashboard/charts.py`) + testes: número de traces, cores por composto/equipe, filtro de outliers e entrada vazia.
9. `feat: app Streamlit` (`dashboard/app.py` + entrypoint) + teste com `streamlit.testing.v1.AppTest` sobre um `data_dir` de fixture (renderiza as quatro abas sem exceção; sem rede).
10. `docs: mkdocs e README`: `docs/index.md`, `guia.md` (extrair e abrir o dashboard), `arquitetura.md` e `api.md` (`::: f1`).

## Verificação

1. `make check` (ou `task lint`, `mypy src`, `task test`, `task docs`): tudo verde, com cobertura ≥ 50%.
2. Extração real:
   ```bash
   poetry run task extract --year 2024 --endpoints meetings,sessions
   poetry run f1-extract --year 2024 --session-key 9472   # corrida do Bahrein 2024
   ```
   Rodar duas vezes e confirmar que a contagem de arquivos e de linhas não muda (idempotência).
3. Dashboard: `poetry run task dashboard` e abrir http://localhost:8501. Selecionar 2024 → Bahrain → Race e conferir as quatro abas:
   - Resultado: 20 pilotos.
   - Ritmo: linhas por piloto com cores das equipes.
   - Pneus: Gantt com compostos e pit stops.
   - Clima: série dentro da janela da corrida.
   Depois, escolher uma sessão fora do cache (ex.: Qualifying) e usar "Baixar dados da sessão".
4. Checklist final do `SKILL.md` conferido item a item.
