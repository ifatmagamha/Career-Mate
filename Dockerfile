# Career Mate API image. Build: docker build -t career-mate-api .
# Runs anywhere that runs containers (Render, Railway, Fly.io, Cloud Run, a VPS). See DEPLOYMENT.md.

# --- build stage: resolve and install dependencies with uv (exact versions from uv.lock) ---
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first: this layer is cached until pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY config ./config
COPY src ./src

# --- runtime stage: no uv, no build tools, not root ---
FROM python:3.14-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_ENV=production
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
# Apply pending migrations, then serve. Hosts set $PORT; --proxy-headers trusts their HTTPS load balancer.
CMD ["sh", "-c", "python -m src.cli migrate && exec uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
