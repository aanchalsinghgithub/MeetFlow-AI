FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg tesseract-ocr curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app
COPY pyproject.toml README.md ./
RUN uv sync --no-dev

RUN uv run playwright install --with-deps chromium

COPY backend ./backend
COPY team_mapping.json ./team_mapping.json
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
