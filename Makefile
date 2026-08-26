.PHONY: install test lint format typecheck check migrate run

install:
	python -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests alembic

format:
	ruff format src tests alembic

typecheck:
	mypy src

check: test lint typecheck
	ruff format --check src tests alembic

migrate:
	alembic upgrade head

run:
	namoz-bot
