# src/webhook_handler/main.py
import json, os
import logging
from fastapi import FastAPI, Request, HTTPException
from google.cloud import pubsub_v1

logging.basicConfig(level=logging.INFO)
logging.info("Starting webhook-handler application")

app = FastAPI()

try:
    logging.info("Initializing PublisherClient")
    publisher = pubsub_v1.PublisherClient()
    logging.info("PublisherClient initialized successfully")
except Exception as e:
    logging.exception(f"Error initializing PublisherClient: {e}")
    publisher = None

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "trading-signals")
if not PROJECT_ID:
    logging.error("GOOGLE_CLOUD_PROJECT environment variable is not set")
    raise RuntimeError("GOOGLE_CLOUD_PROJECT environment variable is required")
else:
    logging.info(f"PROJECT_ID: {PROJECT_ID}")

if not TOPIC_ID:
    logging.error("PUBSUB_TOPIC environment variable is not set")
    raise RuntimeError("PUBSUB_TOPIC environment variable is required")
else:
    logging.info(f"TOPIC_ID: {TOPIC_ID}")

if publisher:
    try:
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        logging.info(f"Topic path: {topic_path}")
    except Exception as e:
        logging.exception(f"Error creating topic path: {e}")
        topic_path = None
else:
    topic_path = None

@app.get("/")
def health():
    logging.info("Health check endpoint called")
    return {"ok": True}

@app.post("/")
async def handle_tradingview(request: Request):
    logging.info("handle_tradingview endpoint called")
    if not publisher or not topic_path:
        logging.error("Publisher or topic path not available")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # TradingView sends application/json ONLY if the message is valid JSON,
    # otherwise it sends text/plain. We support both. :contentReference[oaicite:0]{index=0}
    ctype = (request.headers.get("content-type") or "").lower()
    raw = await request.body()

    if "application/json" in ctype:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")
    else:
        # Treat anything else (e.g., text/plain) as a raw string payload
        payload = {"text": raw.decode("utf-8", errors="replace")}

    # Don't base64-encode manually; the client does it for you. :contentReference[oaicite:1]{index=1}
    data_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    future = publisher.publish(topic_path, data=data_bytes)  # returns a Future
    msg_id = future.result(timeout=10)

    # Return a tiny response so TradingView won’t retry.
    return {"published": True, "message_id": msg_id}