# Argybargy — peer-to-peer bridge for AI agents.
# Build:  docker build -t argybargy .
# Run:    docker run -p 8765:8765 -v argybargy-data:/data argybargy
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARGYBARGY_DATA=/data \
    ARGYBARGY_HOST=0.0.0.0 \
    ARGYBARGY_PORT=8765

WORKDIR /app
COPY pyproject.toml README.md ./
COPY argybargy ./argybargy
RUN pip install . && mkdir -p /data \
    && useradd --create-home --uid 10001 app && chown -R app /data /app
USER app

VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/health').getcode()==200 else 1)"

CMD ["argybargy", "serve", "--host", "0.0.0.0", "--port", "8765"]
