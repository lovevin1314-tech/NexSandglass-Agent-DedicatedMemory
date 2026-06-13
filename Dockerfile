FROM python:3.11-slim

LABEL org.opencontainers.image.title="NexSandglass"
LABEL org.opencontainers.image.description="沙漏记忆系统 — 零依赖 AI Agent 记忆引擎"
LABEL org.opencontainers.image.version="2.9.3"

ENV NEXSANDBASE_HOME=/data

RUN mkdir -p /app /data
WORKDIR /app

COPY scripts/ /app/

RUN pip install --no-cache-dir uv && \
    python -m py_compile sandglass_paths.py && \
    echo "NexSandglass ready"

VOLUME ["/data"]

EXPOSE 8765

CMD ["python", "sandglass_mcp.py"]
