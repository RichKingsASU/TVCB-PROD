import os, json, base64, hashlib, hmac
from flask import Flask, request, jsonify
from google.cloud import pubsub_v1

PROJECT_ID = os.environ["PROJECT_ID"]
TOPIC_NAME = os.environ.get("TOPIC_NAME","trading-signals")
TV_SECRET = os.environ.get("TV_SECRET")
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

app = Flask(__name__)

@app.get("/healthz")
def health():
    return {"status":"ok"}, 200

@app.post("/webhook/tradingview")
def tv_webhook():
    # TradingView posts JSON we define in the alert (no official HMAC header)
    # Use a shared secret sent in a header you control.
    secret = request.headers.get("X-TV-Secret") or (request.get_json(silent=True) or {}).get("secret")
    if not TV_SECRET or secret != TV_SECRET:
        return jsonify({"error":"unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    # minimal validation
    for k in ("symbol","action"):
        if k not in data: return jsonify({"error":f"missing {k}"}), 400

    attrs = {
        "symbol": str(data.get("symbol")),
        "action": str(data.get("action")),
        "strategy": str(data.get("strategy","na")),
        "version": "v1",
    }
    publisher.publish(topic_path, json.dumps(data).encode("utf-8"), **attrs)
    return jsonify({"status":"published","attrs":attrs}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))