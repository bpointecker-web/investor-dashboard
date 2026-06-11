# Investor Dashboard - Task Runner (Make)
# Windows-Hinweis: `make` ist auf Windows oft nicht installiert.
# Aequivalente Befehle stehen in `tasks.ps1` (PowerShell) zur Verfuegung:
#   .\tasks.ps1 install | run | test | lint | typecheck | format | check
#
# Alle Targets nutzen `uv run`, damit kein manuelles venv-Aktivieren noetig ist.

.DEFAULT_GOAL := help
.PHONY: help install run test lint typecheck format check

help: ## Zeigt diese Hilfe
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Installiert alle Abhaengigkeiten via uv (inkl. dev)
	uv sync

run: ## Startet das Dashboard auf http://localhost:8000
	uv run python -m dashboard

test: ## Fuehrt die Testsuite mit Coverage aus
	uv run pytest --cov=src/dashboard --cov-report=term-missing

lint: ## Prueft Code-Stil mit ruff
	uv run ruff check src tests

typecheck: ## Statische Typpruefung mit mypy (strict)
	uv run mypy

format: ## Formatiert Code mit ruff
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint typecheck test ## Lint + Typecheck + Tests (CI-Gate)
