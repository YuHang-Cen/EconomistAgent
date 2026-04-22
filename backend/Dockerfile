FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . /app

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "python scripts/bootstrap_storage.py && uv run serve"]
