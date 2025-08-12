# Stage 1: Builder (install dependencies into a venv)
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

COPY --from=builder /opt/venv /opt/venv
COPY . .

# Healthcheck for /healthz without adding curl
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os, sys; url=f'http://127.0.0.1:{os.getenv("PORT","8000")}/healthz'; sys.exit(0) if urllib.request.urlopen(url).getcode()==200 else sys.exit(1)"

EXPOSE 8000
# Use shell form to expand ${PORT}; enable proxy headers for prod
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"
