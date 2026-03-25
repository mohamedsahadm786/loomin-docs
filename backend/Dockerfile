FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgomp1 \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SENTENCE_TRANSFORMERS_HOME=/app/models_cache
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /app/uploads /app/faiss_index /app/models_cache /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]