WORKDIR /app
COPY src/webhook-handler/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/webhook-handler/ . 
ENV PORT=8080
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]