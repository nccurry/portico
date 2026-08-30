# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.14.7-slim-bookworm

FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM ${PYTHON_IMAGE} AS runtime

ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.title="Portico" \
      org.opencontainers.image.description="A self-hosted personal finance dashboard for Tiller data" \
      org.opencontainers.image.source="https://github.com/nccurry/portico" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN groupadd --gid 10001 portico \
    && useradd --uid 10001 --gid portico --create-home --home-dir /home/portico portico \
    && mkdir -p /app/.local \
    && chown portico:portico /app/.local

ENV PATH="/app/.venv/bin:${PATH}" \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder --chown=portico:portico /app/.venv /app/.venv
COPY --chown=portico:portico Home.py LICENSE README.md ./
COPY --chown=portico:portico .streamlit/config.toml .streamlit/config.toml
COPY --chown=portico:portico config/defaults.toml config/defaults.toml
COPY --chown=portico:portico demo/ demo/
COPY --chown=portico:portico pages/ pages/
COPY --chown=portico:portico src/ src/
COPY --chown=portico:portico scripts/doctor.py scripts/weekly-discord-summary.py scripts/

USER 10001:10001

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3).read()"]

CMD ["streamlit", "run", "Home.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.runOnSave=false", "--client.showErrorDetails=false", "--browser.gatherUsageStats=false"]
