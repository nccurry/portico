# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:b1c8e01d2dcb17a102fdd0abd2d2f4737f2b1be0373944314ef22c39f3c4b931
FROM ${BASE_IMAGE}

USER root

COPY pyproject.toml uv.lock /tmp/portico-dependencies/
COPY --chmod=0755 .devcontainer/install-tools.sh /usr/local/share/portico/install-tools.sh

RUN /usr/local/share/portico/install-tools.sh /tmp/portico-dependencies/pyproject.toml \
    && mkdir -p /opt/portico /home/vscode/.cache/uv \
    && chown -R vscode:vscode /opt/portico /home/vscode/.cache/uv /tmp/portico-dependencies

ENV PORTICO_UV=uv \
    PORTICO_TASK=task \
    PORTICO_VENV=/opt/portico/.venv \
    UV_PROJECT_ENVIRONMENT=/opt/portico/.venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/home/vscode/.cache/uv,uid=1000,gid=1000 \
    su vscode -c "cd /tmp/portico-dependencies && uv sync --locked --dev --no-install-project"

WORKDIR /workspaces/portico
USER vscode
