# syntax=docker/dockerfile:1
# Produktions-Image fuer das Investor Dashboard (uv-basiert, schlank).
FROM python:3.12-slim-bookworm

# uv aus dem offiziellen Image uebernehmen (schnelle, reproduzierbare Installs).
COPY --from=ghcr.io/astral-sh/uv:0.9.20 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DASHBOARD_HOST=0.0.0.0 \
    LOG_JSON=true

WORKDIR /app

# Abhaengigkeiten + Projekt installieren (uv.lock => reproduzierbar).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Cloud-Hoster injizieren $PORT; lokal Standard 8000.
EXPOSE 8000

CMD ["uv", "run", "--no-sync", "python", "-m", "dashboard"]
