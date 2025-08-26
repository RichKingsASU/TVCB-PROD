FROM python:3.11-slim
WORKDIR /app

# Install deps with constraints
COPY src/webhook-handler/requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt && pip check

# App code
COPY src/webhook-handler/ .

ENV PORT=8080
CMD ["gunicorn","-w","2","-b","0.0.0.0:8080","main:app"]
