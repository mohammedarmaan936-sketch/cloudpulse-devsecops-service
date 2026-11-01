# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Create virtual environment and install dependencies without cache
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    find /opt/venv -name "bom.cdx.json" -delete

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Update OS packages and install curl for container health check
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade system packaging tools and clean up unused packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    rm -rf /usr/local/lib/python3.12/site-packages/setuptools* /usr/local/lib/python3.12/site-packages/wheel* && \
    find /usr/local/lib/python3.12 -name "bom.cdx.json" -delete

# Create dedicated non-root system user and group (UID 10001)
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /sbin/nologin -M appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code with non-root ownership
COPY --chown=appuser:appuser app/ ./app/

# Set environment variables for non-root execution
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Native Docker health check hitting the healthz probe
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Start Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

