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
