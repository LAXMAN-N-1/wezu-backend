# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tini \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 && \
    python -m venv "$VIRTUAL_ENV" && \
    addgroup --system --gid 10001 wezu && \
    adduser --system --uid 10001 --ingroup wezu wezu && \
    mkdir -p /app/uploads /app/tmp && \
    chown -R wezu:wezu /app && \
    rm -rf /var/lib/apt/lists/*

FROM base AS builder

ARG REQUIREMENTS_FILE=requirements.prod.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        pkg-config \
        cargo \
        rustc \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libfreetype6-dev && \
    rm -rf /var/lib/apt/lists/*

COPY ${REQUIREMENTS_FILE} /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --prefer-binary --no-cache-dir --wheel-dir /tmp/wheels -r /tmp/requirements.txt

FROM base AS runtime

ARG REQUIREMENTS_FILE=requirements.prod.txt

COPY --from=builder /tmp/wheels /tmp/wheels
COPY ${REQUIREMENTS_FILE} /tmp/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r /tmp/requirements.txt && \
    rm -rf /tmp/wheels /tmp/requirements.txt

COPY --chown=wezu:wezu app /app/app
COPY --chown=wezu:wezu alembic /app/alembic
COPY --chown=wezu:wezu docker /app/docker
COPY --chown=wezu:wezu alembic.ini gunicorn_conf.py /app/

RUN chmod +x /app/docker/entrypoint.sh

USER wezu

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]

FROM runtime AS dev-runtime

USER root
COPY requirements.txt /tmp/requirements.dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements.dev.txt && \
    rm -f /tmp/requirements.dev.txt
USER wezu

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
