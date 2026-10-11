# Local Airflow showcase. Airflow and roshni live in separate Python environments so their
# dependencies never conflict: DAG tasks call /opt/roshni-venv/bin/roshni (the same CLI that
# GitHub Actions runs). GitHub Actions stays the production scheduler.
ARG AIRFLOW_IMAGE=apache/airflow:3.1.0-python3.12
FROM ${AIRFLOW_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md /opt/roshni-src/
COPY src /opt/roshni-src/src
RUN chown -R airflow: /opt/roshni-src

USER airflow
ENV UV_PROJECT_ENVIRONMENT=/opt/roshni-venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
RUN cd /opt/roshni-src && uv sync --frozen --no-dev --python "$(command -v python3)"
