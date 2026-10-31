---
name: python-data-eng-standards
description: Use ao criar projeto Python, adicionar dependência, escrever testes, configurar lint/docs ou revisar/alterar código Python do time de Engenharia de Dados (pipelines, extratores, Lambdas).
---

# Padrões Python — Engenharia de Dados

Siga estas regras sempre que criar, revisar ou alterar código Python do time. Elas valem para pipelines, extratores (AWS Lambda), bibliotecas internas e utilitários. Se uma regra não puder ser cumprida, avise o usuário de forma explícita. Nunca ignore uma regra sem avisar.

## 1. Poetry e layout `src/`

### Regras
- **Sempre** use Poetry 2.x para gerenciar a venv e os pacotes.
- **Nunca** use `pip install`, `pip freeze` nem `requirements.txt` editado à mão.
- **Sempre** use o layout `src/` (estrutura abaixo).
- **Sempre** versione o `poetry.lock` no git.
- **Sempre** configure a venv dentro do projeto (`.venv/`).
- Separe as dependências por grupo: principal (runtime), `dev` e `docs`.
- Quando a Lambda precisar de `requirements.txt`, gere o arquivo com `poetry export`. Nunca escreva esse arquivo à mão.

### Estrutura obrigatória
```
projeto/
├── pyproject.toml
├── poetry.lock
├── poetry.toml              # virtualenvs.in-project = true
├── README.md
├── Makefile
├── mkdocs.yml
├── .pre-commit-config.yaml
├── .gitignore
├── src/
│   └── nome_projeto/
│       ├── __init__.py
│       ├── handler.py       # entrypoint: só orquestra
│       ├── config/
│       ├── clients/         # adaptadores de I/O (S3, APIs, banco)
│       ├── extract/
│       ├── transform/
│       ├── load/
│       └── utils/
├── tests/
│   ├── conftest.py
│   └── unit/                # espelha src/nome_projeto/
└── docs/
```

### Comandos
```bash
poetry new nome-projeto                          # Poetry 2.x já cria o layout src/
poetry config virtualenvs.in-project true --local
poetry install                                   # cria .venv/ e instala tudo
poetry add requests                              # dependência de runtime
poetry add --group dev ruff pytest pytest-cov pytest-mock moto mypy pre-commit
poetry add --group docs mkdocs-material "mkdocstrings[python]"
poetry remove requests
poetry lock                                      # atualiza o lock após editar o pyproject
poetry run <cmd>                                 # executa dentro da venv
poetry env info                                  # mostra a venv em uso
eval $(poetry env activate)                      # ativa a venv (no 2.x, `poetry shell` virou plugin)
```

### Empacotamento para Lambda
```bash
poetry self add poetry-plugin-export
poetry export -f requirements.txt --only main --without-hashes -o build/requirements.txt
```
Coloque o arquivo exportado em `build/` (ignorado pelo git) e nunca o edite.

## 2. Modularidade

- **Sempre** organize o código em módulos coesos, cada um com uma responsabilidade: `config`, `clients`, `extract`, `transform`, `load`, `utils`.
- **Nunca** coloque lógica de negócio no `handler`/`main`. O entrypoint só orquestra.
- Prefira funções pequenas e puras. Deixe o I/O (APIs, S3, banco) em clientes ou adaptadores que possam ser mockados.
- **Sempre** use imports absolutos: `from nome_projeto.extract.api import fetch_orders`.
- **Proibido:** imports circulares, `import *` e variáveis globais mutáveis.
- **Sempre** leia a configuração de variáveis de ambiente em um único módulo (`config/`), usando `pydantic-settings`.
- **Nunca** coloque credenciais no código. Busque os segredos no AWS Secrets Manager ou no SSM Parameter Store.

### Configuração
```python
# src/nome_projeto/config/settings.py
"""Configuração da aplicação lida de variáveis de ambiente."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parâmetros da aplicação."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    bucket_name: str
    api_base_url: str
    api_secret_id: str  # nome do segredo no Secrets Manager, nunca o valor
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações (instância única, imutável)."""
    return Settings()
```

### Handler da Lambda (só orquestra)
```python
# src/nome_projeto/handler.py
"""Entrypoint da Lambda de extração de pedidos."""

import logging
from typing import Any

from nome_projeto.clients.s3 import S3Client
from nome_projeto.config.settings import get_settings
from nome_projeto.extract.api import fetch_orders
from nome_projeto.load.s3 import write_partition
from nome_projeto.transform.orders import normalize_orders

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Orquestra extract -> transform -> load para a data do evento."""
    settings = get_settings()
    run_date = event["run_date"]
    raw = fetch_orders(settings.api_base_url, run_date)
    rows = normalize_orders(raw)
    key = write_partition(S3Client(settings.bucket_name), rows, run_date)
    logger.info("Carga concluída", extra={"run_date": run_date, "rows": len(rows), "key": key})
    return {"status": "ok", "rows": len(rows)}
```

## 3. Ruff (lint, formatação e imports)

- O Ruff é a **única** ferramenta de lint e formatação. **Nunca** adicione black, isort ou flake8.
- A ordenação de imports é feita pelo Ruff (regra `I`).
- Use `# noqa: <REGRA>` só com código específico e com o motivo no comentário. Nunca use `# noqa` sem código.

```bash
poetry run ruff check . --fix        # local
poetry run ruff format .             # local
poetry run ruff check .              # CI
poetry run ruff format --check .     # CI
```

### `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0  # atualize com `poetry run pre-commit autoupdate`
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```
Instale os hooks com `poetry run pre-commit install`.

## 4. Testes com pytest (cobertura mínima de 50%)

- Escreva os testes unitários em `tests/unit/`, espelhando `src/nome_projeto/`. Exemplo: `src/nome_projeto/transform/orders.py` → `tests/unit/transform/test_orders.py`.
- Nomeie arquivos como `test_<modulo>.py` e funções como `test_<comportamento_esperado>()`.
- Use fixtures em `conftest.py`, `pytest.mark.parametrize` para variações e `pytest-mock`/`moto` para AWS e chamadas externas.
- **Nunca** acesse rede, S3 ou banco reais em teste unitário.
- **Toda** função nova ou alterada precisa de teste. Todo bug corrigido ganha um teste de regressão.
- A cobertura mínima é **50%** e o build **quebra** abaixo disso (`--cov-fail-under=50`).
- Rode com `poetry run pytest`.

```python
# tests/conftest.py
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def s3_bucket(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket="bucket-teste")
        yield "bucket-teste"
```

```python
# tests/unit/transform/test_orders.py
import pytest

from nome_projeto.transform.orders import normalize_orders


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([{"id": "1", "valor": "10.5"}], [{"id": 1, "valor": 10.5}]),
        ([], []),
    ],
)
def test_normalize_orders_converte_tipos(raw: list[dict], expected: list[dict]) -> None:
    assert normalize_orders(raw) == expected


def test_fetch_orders_nao_chama_rede_real(mocker) -> None:
    get = mocker.patch("nome_projeto.extract.api.requests.get")
    get.return_value.json.return_value = []
    ...
```

## 5. Documentação (mkdocs-material + mkdocstrings)

- Mantenha a documentação em `docs/`. A referência da API é gerada a partir das docstrings.
- **Sempre** escreva docstrings no padrão Google em módulos, classes e funções públicas.
- Rode `poetry run mkdocs serve` localmente e `poetry run mkdocs build --strict` no CI e antes de entregar.
- Mantenha o README curto: o que é, como instalar (`poetry install`), como rodar, como testar e link para a doc.

```python
def normalize_orders(raw: list[dict[str, str]]) -> list[dict[str, float | int]]:
    """Normaliza pedidos brutos da API.

    Args:
        raw: Lista de pedidos como retornados pela API.

    Returns:
        Lista de pedidos com tipos convertidos.

    Raises:
        InvalidOrderError: Se um pedido não tiver o campo `id`.
    """
```

### `mkdocs.yml`
```yaml
site_name: nome-projeto
theme:
  name: material
  language: pt-BR
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: false
nav:
  - Início: index.md
  - Guia de uso: guia.md
  - Arquitetura: arquitetura.md
  - Referência da API: api.md
```
O arquivo `docs/api.md` contém `::: nome_projeto`.

## 6. Boas práticas Python

- **Sempre** use type hints em funções públicas e valide com `poetry run mypy src`.
- **Sempre** use `logging` com um logger por módulo: `logger = logging.getLogger(__name__)`. **Nunca** use `print`.
- Para logs estruturados, passe o contexto em `extra={...}` e não interpole dados sensíveis.
- **Nunca** use `except:` nu nem `except Exception: pass`. Capture exceções específicas e faça log ou relance com `raise ... from err`.
- Crie exceções de domínio quando fizer sentido. Exemplo: `class InvalidOrderError(ValueError): ...`.
- Use `pathlib` em vez de `os.path`, f-strings, `dataclasses`/`pydantic` para estruturas de dados e context managers (`with`) para recursos.
- **Sempre** projete pipelines idempotentes. Grave por partição determinística (ex.: `dt=2026-10-30/`) com sobrescrita ou upsert, para que reprocessar não duplique dados.
- Fixe `requires-python` no `pyproject.toml` e alinhe com o runtime da Lambda (ex.: `python3.12`).
- Prefira commits pequenos no padrão Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).

### `.gitignore` mínimo
```
.venv/
__pycache__/
.coverage
htmlcov/
site/
build/
.env
.mypy_cache/
.ruff_cache/
.pytest_cache/
```

## 7. Exemplo completo de `pyproject.toml`

```toml
[project]
name = "nome-projeto"
version = "0.1.0"
description = "Extrator de pedidos para o data lake."
readme = "README.md"
requires-python = ">=3.12,<3.13"  # alinhado ao runtime python3.12 da Lambda
dependencies = [
    "boto3>=1.35",
    "requests>=2.32",
    "pydantic-settings>=2.4",
]

[tool.poetry]
packages = [{ include = "nome_projeto", from = "src" }]

[tool.poetry.requires-plugins]
poetry-plugin-export = ">=1.8"

[tool.poetry.group.dev.dependencies]
ruff = "^0.14"
pytest = "^8.3"
pytest-cov = "^6.0"
pytest-mock = "^3.14"
moto = { version = "^5.0", extras = ["s3", "secretsmanager"] }
mypy = "^1.13"
pre-commit = "^4.0"
boto3-stubs = { version = "^1.35", extras = ["s3"] }
types-requests = "^2.32"

[tool.poetry.group.docs.dependencies]
mkdocs-material = "^9.5"
mkdocstrings = { version = "^0.27", extras = ["python"] }

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

# ---------- Ruff ----------
[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "N", "C4", "PL", "RUF", "S"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",    # assert é o mecanismo do pytest
    "PLR2004", # valores literais são esperados em asserts
    "S105",    # credenciais falsas em fixtures
]

[tool.ruff.lint.isort]
known-first-party = ["nome_projeto"]

[tool.ruff.format]
quote-style = "double"

# ---------- Pytest / Coverage ----------
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src/nome_projeto --cov-report=term-missing --cov-fail-under=50"

[tool.coverage.run]
source = ["src/nome_projeto"]
branch = true
omit = ["tests/*"]

[tool.coverage.report]
show_missing = true
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "raise NotImplementedError"]

# ---------- Mypy ----------
[tool.mypy]
python_version = "3.12"
files = ["src"]
strict = true
plugins = ["pydantic.mypy"]
```

## 8. Comandos de qualidade (rode nesta ordem antes de entregar)

```bash
poetry install
poetry run ruff check . --fix
poetry run ruff format .
poetry run mypy src
poetry run pytest
poetry run mkdocs build --strict
```

### `Makefile` (só chama `poetry run`)
```makefile
.PHONY: install lint format typecheck test docs check

install:
	poetry install

lint:
	poetry run ruff check .
	poetry run ruff format --check .

format:
	poetry run ruff check . --fix
	poetry run ruff format .

typecheck:
	poetry run mypy src

test:
	poetry run pytest

docs:
	poetry run mkdocs build --strict

check: lint typecheck test docs
```

## 9. Faça / Não faça

| Não faça | Faça |
|---|---|
| `pip install pacote` | `poetry add pacote` (ou `--group dev`/`docs`) |
| Editar `requirements.txt` à mão | `poetry export --only main` |
| Deixar `poetry.lock` fora do git | Versionar `poetry.lock` |
| `print("debug")` | `logger.info(...)` com `logging.getLogger(__name__)` |
| Lógica de negócio no `handler` | Lógica em `transform/`/`extract/`; o handler só orquestra |
| `boto3.client` espalhado pelo código | Cliente em `clients/` injetado e mockável |
| `except: pass` / `except Exception: pass` | Capturar exceção específica, logar ou relançar |
| `os.path.join(a, b)` | `Path(a) / b` |
| Senha/token no código ou no `.env` versionado | Secrets Manager / SSM, lido via `config/` |
| `from modulo import *` / imports relativos | Imports absolutos `from nome_projeto.x import y` |
| black + isort + flake8 | Apenas Ruff |
| Teste que chama S3/API real | `moto` / `pytest-mock` |
| `INSERT` cego que duplica em reprocessamento | Escrita por partição com sobrescrita/upsert |

## 10. Criar um projeto novo do zero

1. `poetry new nome-projeto && cd nome-projeto`
2. `poetry config virtualenvs.in-project true --local`
3. Ajuste o `pyproject.toml` conforme a seção 7 (`requires-python`, ruff, pytest, coverage, mypy).
4. Adicione as dependências:
   ```bash
   poetry add boto3 requests pydantic-settings
   poetry add --group dev ruff pytest pytest-cov pytest-mock "moto[s3]" mypy pre-commit
   poetry add --group docs mkdocs-material "mkdocstrings[python]"
   poetry self add poetry-plugin-export
   ```
5. Crie as pastas `config/`, `clients/`, `extract/`, `transform/`, `load/`, `utils/` (com `__init__.py`) e `tests/unit/` espelhado.
6. Crie `.gitignore`, `.pre-commit-config.yaml`, `mkdocs.yml`, `docs/` (index, guia, arquitetura, api), `Makefile` e o README.
7. `poetry install && poetry run pre-commit install`
8. Escreva o primeiro módulo com teste e rode `make check`.
9. Faça o commit incluindo o `poetry.lock`: `git commit -m "chore: estrutura inicial do projeto"`.

## Checklist antes de entregar

Confira **todos** os itens antes de concluir qualquer tarefa. Se algum falhar, corrija ou informe o usuário de forma explícita.

- [ ] Nenhum uso de pip; dependência adicionada via `poetry add` no grupo certo
- [ ] `poetry.lock` atualizado e versionado
- [ ] Código dentro de `src/<pacote>/`, modular e sem lógica no entrypoint
- [ ] Imports absolutos, sem `import *`, sem imports circulares e sem globais mutáveis
- [ ] `ruff check` e `ruff format --check` passando (imports organizados)
- [ ] Type hints + mypy sem erros
- [ ] Testes unitários escritos (sem rede/S3/banco reais); cobertura ≥ 50%
- [ ] Bug corrigido tem teste de regressão
- [ ] `logging` em vez de `print`; nenhum `except` nu ou silencioso
- [ ] Docstrings Google e doc atualizada; `mkdocs build --strict` passando
- [ ] Sem segredos ou credenciais no código; configuração centralizada em `config/`
- [ ] Pipeline idempotente (reprocessar não duplica dados)
