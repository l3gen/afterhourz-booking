# Local development. No AWS account needed: DynamoDB is emulated with moto's server.
PY ?= python3
VENV := .venv
BIN := $(CURDIR)/$(VENV)/bin
export AWS_ACCESS_KEY_ID ?= local
export AWS_SECRET_ACCESS_KEY ?= local
export AWS_DEFAULT_REGION ?= us-east-1

.PHONY: help setup db api web test lint

help:
	@echo "make setup   install backend + frontend dependencies"
	@echo "make db      start local DynamoDB (moto) on :8001 and create the table"
	@echo "make api     run the API on :8000 (dev sign-in enabled)"
	@echo "make web     run the site on :5173 (proxies /api to :8000)"
	@echo "make test    run all tests"
	@echo "make lint    ruff + eslint"
	@echo "Run db, api and web in three terminals, then open http://localhost:5173"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

db:
	@($(BIN)/moto_server -p 8001 >/dev/null 2>&1 &) ; sleep 2
	cd backend && DYNAMODB_ENDPOINT_URL=http://localhost:8001 $(BIN)/python scripts/create_table.py
	@echo "DynamoDB (moto) running on :8001. Data resets when you stop it."

api:
	cd backend && ENV=local DEV_LOGIN_ENABLED=true ADMIN_EMAILS=$${ADMIN_EMAILS:-owner@example.com} \
	  DYNAMODB_ENDPOINT_URL=http://localhost:8001 TABLE_NAME=afterhourz-local \
	  $(BIN)/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && $(BIN)/python -m pytest
	cd lambdas && $(BIN)/python -m pytest
	cd frontend && npm test

lint:
	$(BIN)/ruff check backend lambdas && $(BIN)/ruff format --check backend lambdas
	cd frontend && npm run lint
