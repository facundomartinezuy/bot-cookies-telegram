FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usamos gunicorn para manejar el servidor en producción
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app