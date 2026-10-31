# Guia de uso

## Instalação

Requer Python 3.12 e Poetry 2.x.

```bash
poetry install
```

A venv é criada em `.venv/` (configurado em `poetry.toml`).

## Abrindo o dashboard

```bash
poetry run task dashboard        # ou: poetry run f1-dashboard
```

Abra <http://localhost:8501>. Na barra lateral, escolha a temporada, o Grande Prêmio,
a sessão e os pilotos.

- Se o calendário da temporada não estiver no cache, clique em **Baixar calendário**.
- Se a sessão não estiver no cache, clique em **Baixar dados da sessão** (leva alguns
  segundos por causa do intervalo mínimo entre requisições).

Argumentos extras vão para o Streamlit, por exemplo `poetry run f1-dashboard --server.port 8502`.

## Pré-carregando dados pela linha de comando

```bash
# Calendário (meetings e sessions) da temporada
poetry run task extract --year 2024 --endpoints meetings,sessions

# Todos os dados de uma sessão (9472 = corrida do Bahrein 2024)
poetry run f1-extract --year 2024 --session-key 9472

# Temporada inteira (demorado: várias requisições por sessão)
poetry run f1-extract --year 2024
```

| Opção | Descrição |
|---|---|
| `--year` | Temporada (obrigatório). |
| `--endpoints` | Lista separada por vírgula. Padrão: todos. |
| `--session-key` | Restringe os endpoints por sessão/meeting a uma sessão. |
| `--log-level` | Sobrescreve `F1_LOG_LEVEL`. |

O código de saída é `0` quando tudo foi extraído e `1` quando alguma partição falhou.
Reexecutar sobrescreve as partições, sem duplicar dados.

## Configuração

Variáveis de ambiente (ou arquivo `.env`) com prefixo `F1_`:

| Variável | Padrão | Descrição |
|---|---|---|
| `F1_API_BASE_URL` | `https://api.openf1.org/v1` | URL base da API. |
| `F1_DATA_DIR` | `data` | Diretório do cache (lido pelo dashboard). |
| `F1_REQUEST_TIMEOUT` | `30` | Timeout por requisição (s). |
| `F1_MAX_RETRIES` | `3` | Novas tentativas em 429/5xx/timeout. |
| `F1_MIN_INTERVAL_SECONDS` | `0.5` | Intervalo mínimo entre requisições (s). |
| `F1_LOG_LEVEL` | `INFO` | Nível de log do extrator. |

## Desenvolvimento

```bash
poetry run task format   # ruff check --fix + ruff format
poetry run task lint     # ruff check + ruff format --check
poetry run task test     # pytest com cobertura >= 50%
poetry run task docs     # mkdocs build --strict (gera site/)
poetry run task docs-serve  # documentação com recarga automática em http://localhost:8000
poetry run task --list   # lista todas as tasks
make check               # lint, mypy, pytest e docs
```
