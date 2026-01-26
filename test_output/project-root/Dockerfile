# syntax=docker/dockerfile:1

# ---- Builder Stage ----
# Install dependencies into a virtual environment to keep the final image clean.
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VENV_PATH=/opt/venv

RUN python -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt gunicorn

# ---- Final Stage ----
# Create the lean, final production image.
FROM python:3.11-slim-bookworm AS final

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VENV_PATH=/opt/venv
ENV PATH="$VENV_PATH/bin:$PATH"

RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app

COPY --from=builder $VENV_PATH $VENV_PATH
COPY src/ ./src/

RUN python -m compileall .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('127.0.0.1', 5000))"

CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:5000", "src.main:app"]