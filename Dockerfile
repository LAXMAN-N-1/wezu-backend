# ---- Build Stage ----
FROM python:3.11-slim as builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ---- Final Stage ----
FROM python:3.11-slim

# Create a non-root user
RUN adduser --disabled-password --gecos '' wezu_user

WORKDIR /app
ENV PYTHONPATH=/app

# Install runtime dependencies (like postgres libs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

COPY . .

# Change ownership to non-root user
RUN chown -R wezu_user:wezu_user /app

USER wezu_user

EXPOSE 8000

# Use Gunicorn with Uvicorn workers for production load handling
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--log-level", "info"]
