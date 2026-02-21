FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Optional: generate processed CSVs for demo at build time

CMD ["sh", "-c", "python -m gunicorn --bind 0.0.0.0:${PORT:-5000} wsgi:app"]
