# F1

[![CI](https://github.com/Geovaniof96/F1/actions/workflows/ci.yml/badge.svg)](https://github.com/Geovaniof96/F1/actions/workflows/ci.yml)

Dashboard interativo (Streamlit + Plotly) de dados históricos da Fórmula 1, alimentado pela
API pública [OpenF1](https://openf1.org). Mostra resultado, ritmo por volta, estratégia de
pneus e clima de cada sessão, a partir de um cache local em Parquet.

## Instalação

```bash
poetry install
```

## Uso

```bash
poetry run task dashboard                                       # abre http://localhost:8501
poetry run task extract --year 2024 --endpoints meetings,sessions   # pré-carrega o calendário
poetry run f1-extract --year 2024 --session-key 9472            # pré-carrega uma sessão
```

No dashboard, sessões fora do cache podem ser baixadas por um botão.

## Testes e qualidade

```bash
poetry run task format   # corrige lint e formata (Ruff)
poetry run task lint     # ruff check + ruff format --check
poetry run task test     # pytest com cobertura >= 50%
poetry run task docs     # mkdocs build --strict
make check               # tudo acima + mypy
```

## Documentação

Publicada em <https://geovaniof96.github.io/F1/> a cada push na `main` (via CI).
Feita com mkdocs-material (fonte em [`docs/`](docs/index.md)):

```bash
poetry run task docs         # gera o site em site/ (modo strict)
poetry run task docs-serve   # abre em http://localhost:8000 com recarga automática
```
