.PHONY: dev mongo install test lint typecheck check seed frontend

mongo:
	docker compose up -d mongo

install:
	pip install -e ".[dev]"

dev: mongo
	uvicorn atlaslens.api.main:app --reload

seed:
	python -m atlaslens.cli.seed_admin --username admin

test:
	pytest -q

lint:
	ruff check backend/
	black --check backend/

typecheck:
	mypy backend/atlaslens/

check: lint typecheck test

frontend:
	cd frontend && npm install && npm run dev
