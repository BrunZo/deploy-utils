FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /data/root /data/auth \
    && chmod 0777 /data/root /data/auth

COPY models.py engine.py auth.py core.py routes.py app.py index.html ./

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-tmp-dir", "/tmp", "app:app"]
