FROM python:3.11-slim

# Faster, cleaner Python logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps with constraints and verify integrity
COPY src/webhook-handler/requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt && pip check

# Copy app code
COPY src/webhook-handler/ .

# Drop privileges
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run provides $PORT; keep a sane default for local
ENV PORT=8080
CMD ["sh","-c","exec gunicorn --chdir /app -w 2 -b :${PORT:-8080} --access-logfile - --error-logfile - main:app"]
