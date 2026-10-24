FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV PORT=8765

EXPOSE 8765

CMD ["sh", "-c", "uvicorn trailhead.server:app --host 0.0.0.0 --port ${PORT}"]
