FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY src/trade-executor/requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt && pip check

COPY src/trade-executor/ .

# Run as non-root
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8080
CMD ["sh","-c","exec gunicorn --chdir /app -w 2 -b :${PORT:-8080} --access-logfile - --error-logfile - main:app"]
