# syntax=docker/dockerfile:1.7

# ---------- build: resolve and install dependencies into a venv ----------
FROM python:3.12-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY pyproject.toml ./
COPY src ./src
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install ".[dev]"; else pip install .; fi

# ---------- runtime: slim, non-root ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src:/app \
    DJANGO_SETTINGS_MODULE=config.settings \
    MEDIA_ROOT=/app/media STATIC_ROOT=/app/staticfiles
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app . .
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles \
    && chmod +x docker/entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["web"]
