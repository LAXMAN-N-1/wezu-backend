# ---- Build Stage ----
FROM python:3.11-slim as builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120
ARG REQUIREMENTS_FILE=requirements.prod.txt

# Install build dependencies required by native Python packages.
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

# Install python dependencies
COPY ${REQUIREMENTS_FILE} /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip wheel --prefer-binary --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ---- Final Stage ----
FROM python:3.11-slim

# Create a non-root user
RUN adduser --disabled-password --gecos '' wezu_user

WORKDIR /app
ENV PYTHONPATH=/app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120

# Install runtime shared libraries required by built wheels.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

COPY . .

# Change ownership to non-root user
RUN chown -R wezu_user:wezu_user /app

USER wezu_user

EXPOSE 8000

# Use conservative defaults for small VPS instances.
# Run migrations then start the app server.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app --workers ${GUNICORN_WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --log-level ${GUNICORN_LOG_LEVEL:-info} --access-logfile - --error-logfile - --capture-output --timeout ${GUNICORN_TIMEOUT:-60} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} --max-requests ${GUNICORN_MAX_REQUESTS:-1000} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100}"]
