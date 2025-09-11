# src/webhook_handler/main.py
import json, os
from fastapi import FastAPI, Request, HTTPException
from google.cloud import pubsub_v1

app = FastAPI()

PROJECT_ID = os.environ.get("PROJECT_ID")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "trading-signals")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.get("/")
def health():
    return {"ok": True}

@app.post("/")
async def handle_tradingview(request: Request):
    # Verify shared secret
    shared_secret = os.environ.get("SHARED_SECRET")
    if shared_secret:
        request_secret = request.headers.get("X-Shared-Secret")
        if request_secret != shared_secret:
            raise HTTPException(status_code=403, detail="Invalid shared secret")

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
    future = publisher.publish(
        topic_path,
        data=data_bytes,
        source="tradingview",
        strategy="utbot",
        action=payload.get("action", ""),
        timeframe=payload.get("timeframe", ""),
        symbol=payload.get("symbol", ""),
        content_type="application/json"
    )
    msg_id = future.result(timeout=10)

    # Return a tiny response so TradingView won’t retry.
    return {"published": True, "message_id": msg_id}
