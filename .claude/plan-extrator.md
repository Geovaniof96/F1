# Plano — Extrator OpenF1 (`f1`)

## Contexto

Projeto de aula: um extrator em Python que baixa dados históricos da Fórmula 1 da API pública OpenF1 (ver `doc_api.md`) e grava localmente em JSON (bruto) e Parquet (tratado). Todo o código segue o `SKILL.md` (Poetry 2.x, layout `src/`, Ruff, pytest com cobertura ≥ 50%, mypy, mkdocs-material).

Estado atual do repositório:
- `pyproject.toml` gerado pelo `poetry new` (pacote `f1` em `src/`), sem dependências, com `requires-python = ">=3.15"` e autor placeholder.
- `src/f1/__init__.py` e `tests/__init__.py` vazios.
- `.python-version` = `3.12.10` (pyenv), Poetry 2.5.1 instalado.
- `README.md` só com o título.

### Decisões
- **Destino:** local, sem AWS. `data/raw/` (JSON como veio da API) e `data/processed/` (Parquet).
- **Escopo v1 (núcleo de corrida):** `meetings`, `sessions`, `drivers`, `laps`, `session_result`, `pit`, `stints`, `weather`.
- **Fora da v1:** `car_data`, `location` (telemetria de ~3.7 Hz, alto volume), `intervals`, `position`, `overtakes`, `race_control`, `team_radio`, `championship_*`, `starting_grid`.
- **Entrypoint:** CLI (`f1-extract`), e não um handler de Lambda.

### Desvios do SKILL.md (avisados de forma explícita)
| Regra do SKILL | Neste projeto | Motivo |
|---|---|---|
| `handler.py` de Lambda | `cli.py` + `pipeline.py` | Execução local; o CLI só orquestra, como o handler faria |
| boto3 / moto / S3 | Não usados | Destino local; testes de I/O usam `tmp_path` |
| Segredos no Secrets Manager/SSM | Não há segredos | Dados históricos da OpenF1 são abertos |
| `poetry export` para Lambda | Não aplicável | Sem empacotamento para Lambda |

A camada `load/` fica atrás de uma interface (`Writer`), para que um writer de S3 possa entrar no futuro sem mexer no restante.

## Arquitetura

```
src/f1/
├── __init__.py
├── cli.py                 # argparse -> chama pipeline.run (sem lógica)
├── pipeline.py            # orquestra extract -> transform -> load
├── exceptions.py          # F1Error, OpenF1APIError, InvalidRecordError
├── config/
│   └── settings.py        # Settings (pydantic-settings, prefixo F1_)
├── clients/
│   └── openf1.py          # OpenF1Client: requests.Session, retry/backoff, rate limit
├── extract/
│   ├── endpoints.py       # registro dos 8 endpoints: nome, escopo, chaves primárias
│   └── openf1.py          # fetch_meetings, fetch_sessions, fetch_by_session
├── transform/
│   └── normalize.py       # datas ISO -> datetime, metadados, dedupe por chave
├── load/
│   ├── base.py            # Protocol Writer
│   └── local.py           # LocalWriter: JSON bruto + Parquet, escrita atômica
└── utils/
    └── logging.py         # setup_logging(level)
```

### Fluxo
1. `f1-extract --year 2024 [--endpoints laps,pit] [--session-key 9158]`
2. `pipeline.run(year, endpoints, client, writer)`:
   - busca `meetings` e `sessions` do ano (filtro `?year=`);
   - para cada `session_key` e cada endpoint por sessão (`drivers`, `laps`, `session_result`, `pit`, `stints`), chama `/endpoint?session_key=N`;
   - `weather` é filtrado por `meeting_key`;
   - normaliza e grava cada partição.
3. Resumo no log: endpoints, partições, linhas e falhas.

### Registro de endpoints (`extract/endpoints.py`)
`@dataclass(frozen=True) EndpointSpec(name, scope, primary_keys)`, em que `scope` ∈ {`year`, `meeting`, `session`}.

| Endpoint | Escopo | Chave primária (dedupe) |
|---|---|---|
| meetings | year | meeting_key |
| sessions | year | session_key |
| drivers | session | session_key, driver_number |
| laps | session | session_key, driver_number, lap_number |
| session_result | session | session_key, driver_number |
| pit | session | session_key, driver_number, lap_number |
| stints | session | session_key, driver_number, stint_number |
| weather | meeting | meeting_key, date |

### Cliente HTTP (`clients/openf1.py`)
- `OpenF1Client(base_url, timeout, max_retries, min_interval, session=None)`, que funciona como context manager e fecha a `Session` ao sair.
- `get(endpoint: str, params: dict) -> list[dict[str, Any]]`.
- Retry com backoff exponencial em 429/5xx e timeout. Depois de esgotar as tentativas, lança `OpenF1APIError` (`raise ... from err`).
- Respeita um intervalo mínimo entre requisições (`min_interval`, configurável), por ser uma API comunitária com rate limit.
- Resposta 404 ou lista vazia: retorna `[]` e registra um warning, sem falhar o pipeline.

### Config (`config/settings.py`)
`Settings` com `env_prefix="F1_"`:
- `api_base_url = "https://api.openf1.org/v1"`
- `data_dir: Path = Path("data")`
- `request_timeout = 30`
- `max_retries = 3`
- `min_interval_seconds = 0.5`
- `log_level = "INFO"`

Acesso por `get_settings()` com `@lru_cache`.

### Transform (`transform/normalize.py`, funções puras)
- `parse_dates(record)`: campos `date*` em ISO viram `datetime` (`datetime.fromisoformat`).
- `add_metadata(records, endpoint, extracted_at)`: adiciona `_endpoint` e `_extracted_at`.
- `deduplicate(records, keys)`: mantém o último registro por chave primária; registro sem chave lança `InvalidRecordError`.
- `normalize(records, spec, extracted_at)`: compõe as funções acima.

### Load (`load/local.py`) — idempotente
- Partições determinísticas:
  - `data/raw/<endpoint>/year=YYYY/[meeting_key=M/][session_key=S/]data.json`
  - `data/processed/<endpoint>/year=YYYY/.../data.parquet`
- Escrita atômica: grava em arquivo `.tmp` no mesmo diretório e depois `Path.replace()`. Reprocessar sobrescreve a partição, então nunca duplica dados.
- Parquet com `pyarrow` (`pa.Table.from_pylist` + `pq.write_table`). Lista vazia não gera arquivo.

## Dependências

```bash
poetry add requests pydantic-settings pyarrow
poetry add --group dev ruff pytest pytest-cov pytest-mock mypy pre-commit types-requests pyarrow-stubs
poetry add --group docs mkdocs-material "mkdocstrings[python]"
```

## Fases de implementação (um commit por fase, Conventional Commits)

### Fase 0 — Ambiente e tooling (`chore: configura tooling do projeto`)
- `pyproject.toml`:
  - corrigir `requires-python` para `">=3.12,<3.13"` (alinhado ao `.python-version` 3.12.10);
  - corrigir `description` e `authors`;
  - adicionar `[project.scripts] f1-extract = "f1.cli:main"`;
  - copiar os blocos ruff/pytest/coverage/mypy da seção 7 do SKILL, trocando `nome_projeto` por `f1` e removendo o plugin de export e as libs AWS.
- `poetry config virtualenvs.in-project true --local` (gera `poetry.toml`), seguido de `poetry env use $(pyenv which python)` e `poetry install`.
- Criar `.gitignore` (lista do SKILL + `data/`), `.pre-commit-config.yaml`, `Makefile` (seção 8 do SKILL) e rodar `poetry run pre-commit install`.
- Criar a árvore `src/f1/{config,clients,extract,transform,load,utils}/__init__.py` e `tests/unit/` espelhado, com `tests/conftest.py`.

### Fase 1 — Base (`feat: settings, logging e exceções`)
- `config/settings.py`, `utils/logging.py`, `exceptions.py` + testes.

### Fase 2 — Cliente (`feat: cliente HTTP da OpenF1`)
- `clients/openf1.py` + testes com `pytest-mock` (mock de `Session.get`): sucesso, retry em 429/500, erro após `max_retries`, 404 → `[]`, intervalo mínimo respeitado (mock de `time.sleep`/`time.monotonic`).

### Fase 3 — Extract (`feat: extração dos endpoints núcleo`)
- `extract/endpoints.py` + `extract/openf1.py` + testes com um `FakeClient` em `conftest.py`, verificando que os parâmetros corretos (`year`, `session_key`, `meeting_key`) são enviados.

### Fase 4 — Transform (`feat: normalização e dedupe`)
- `transform/normalize.py` + testes parametrizados: datas, metadados, dedupe, registro sem chave.

### Fase 5 — Load (`feat: writer local JSON/Parquet idempotente`)
- `load/base.py` e `load/local.py` + testes com `tmp_path`: caminho da partição, conteúdo JSON, leitura do Parquet, segunda execução sem duplicar dados, lista vazia sem arquivo.

### Fase 6 — Pipeline e CLI (`feat: pipeline e CLI f1-extract`)
- `pipeline.py` (`run(...) -> RunSummary`): falha em um endpoint ou sessão é registrada no log e contada, sem derrubar as demais.
- `cli.py`: argparse (`--year` obrigatório, `--endpoints`, `--session-key`, `--log-level`). Monta `Settings`, o client e o writer e chama `run`; o código de saída é diferente de 0 se houver falhas.
- Testes: pipeline com `FakeClient` + `LocalWriter(tmp_path)`; parsing de argumentos do CLI.

### Fase 7 — Documentação (`docs: mkdocs e README`)
- `mkdocs.yml` (seção 5 do SKILL, com `site_name: f1`).
- `docs/index.md`, `docs/guia.md` (instalação e exemplos do CLI), `docs/arquitetura.md` (fluxo, partições, endpoints), `docs/api.md` (`::: f1`).
- `README.md` curto: o que é, `poetry install`, como rodar, como testar e link para a doc.
- Docstrings Google em todos os módulos e funções públicas.

## Verificação

1. `make check`: ruff (check + format --check), mypy strict, pytest com cobertura ≥ 50% e `mkdocs build --strict`, tudo verde.
2. Execução real (rede):
   ```bash
   poetry run f1-extract --year 2024 --endpoints meetings,sessions
   poetry run f1-extract --year 2024 --session-key <uma sessão de corrida> --endpoints drivers,laps,pit,stints,session_result
   ```
   Conferir os arquivos em `data/raw/` e `data/processed/`, e ler um Parquet com `poetry run python -c "import pyarrow.parquet as pq; print(pq.read_table('<arquivo>').num_rows)"`.
3. Idempotência: rodar o mesmo comando duas vezes e confirmar que a contagem de arquivos e de linhas não muda.
4. Checklist final do `SKILL.md` conferido item a item.
