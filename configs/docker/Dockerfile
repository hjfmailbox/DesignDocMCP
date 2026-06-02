FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

ENV DESIGNDOC_DATA_DIR=/data
ENV DESIGNDOC_TRANSPORT=http
ENV DESIGNDOC_HOST=0.0.0.0
ENV DESIGNDOC_PORT=8765
ENV PATH="/app/.venv/bin:$PATH"

VOLUME ["/data"]

EXPOSE 8765

ENTRYPOINT ["designdoc-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
