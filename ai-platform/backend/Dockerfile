FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["sh", "-c", "python -m app.db.bootstrap && FIXMEAPP_SKIP_STARTUP_BOOTSTRAP=1 python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
