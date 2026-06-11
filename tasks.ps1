<#
.SYNOPSIS
    Task-Runner fuer das Investor Dashboard (PowerShell-Aequivalent zum Makefile).

.DESCRIPTION
    Native Windows-Alternative, da `make` hier i.d.R. nicht installiert ist.
    Alle Befehle nutzen `uv run`, damit kein manuelles venv-Aktivieren noetig ist.

.EXAMPLE
    .\tasks.ps1 install
    .\tasks.ps1 run
    .\tasks.ps1 check
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'run', 'test', 'lint', 'typecheck', 'format', 'check')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'

function Invoke-Lint      { uv run ruff check src tests }
function Invoke-Typecheck { uv run mypy }
function Invoke-Test      { uv run pytest --cov=src/dashboard --cov-report=term-missing }

switch ($Task) {
    'install'   { uv sync }
    'run'       { uv run python -m dashboard }
    'test'      { Invoke-Test }
    'lint'      { Invoke-Lint }
    'typecheck' { Invoke-Typecheck }
    'format' {
        uv run ruff format src tests
        uv run ruff check --fix src tests
    }
    'check' {
        Invoke-Lint
        Invoke-Typecheck
        Invoke-Test
    }
    default {
        Write-Host "Investor Dashboard - verfuegbare Tasks:" -ForegroundColor Cyan
        Write-Host "  install     Installiert Abhaengigkeiten (uv sync)"
        Write-Host "  run         Startet das Dashboard (http://localhost:8000)"
        Write-Host "  test        Testsuite + Coverage"
        Write-Host "  lint        ruff check"
        Write-Host "  typecheck   mypy --strict"
        Write-Host "  format      ruff format + --fix"
        Write-Host "  check       lint + typecheck + test (CI-Gate)"
    }
}
