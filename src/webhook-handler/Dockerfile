FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN ls -l /app
ENV PORT=8080
CMD ["python", "-m", "gunicorn","-w","2","-b","0.0.0.0:8080","main:app"]
