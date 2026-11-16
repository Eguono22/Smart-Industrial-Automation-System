FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV SIAS_DATABASE_PATH=/app/instance/sias.sqlite3
ENV SIAS_MODEL_PATH=/app/instance/predictor_model.pkl

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

RUN useradd --create-home --uid 10001 sias \
    && mkdir -p /app/instance \
    && chown -R sias:sias /app/instance
USER sias

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '5000') + '/ready', timeout=4)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "server:app"]
