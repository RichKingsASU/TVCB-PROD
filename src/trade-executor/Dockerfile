FROM python:3.11-slim
WORKDIR /app
COPY src/trade-executor/requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt && pip check
COPY src/trade-executor/ . 
ENV PORT=8080
CMD ["sh","-c","exec gunicorn -w 2 -b :${PORT:-8080},"main:app"]