import os, json, base64, logging
from flask import Flask, request, jsonify
from coinbase.rest import RESTClient

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
TRADING_MODE = os.environ.get("TRADING_MODE","PREVIEW").upper()

# RESTClient reads COINBASE_API_KEY / COINBASE_API_SECRET from env
cb = RESTClient()

 @app.get("/healthz")
def health():
    return {"status":"ok","mode":TRADING_MODE}, 200

 @app.post("/pubsub")
def pubsub_push():
    # Pub/Sub push: envelope with base64 data
    envelope = request.get_json(force=True, silent=True) or {}
    msg = envelope.get("message", {})
    data_b64 = msg.get("data")
    if not data_b64:
        return jsonify({"error":"no-data"}), 400
    payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    symbol = payload.get("symbol","BTC-USD").replace("/","-")
    action = payload.get("action","buy").lower()

    # PREVIEW endpoints in SDK for safe testing; LIVE uses market_order_*.
    try:
        if TRADING_MODE == "PREVIEW":
            if action == "buy":
                res = cb.preview_market_order_buy(product_id=symbol, quote_size="5")
            else:
                res = cb.preview_market_order_sell(product_id=symbol, base_size="0.0001")
        else:
            if action == "buy":
                res = cb.market_order_buy(product_id=symbol, quote_size="5")
            else:
                res = cb.market_order_sell(product_id=symbol, base_size="0.0001")
        logging.info("Order response: %s", res)
        return jsonify({"status":"ok","mode":TRADING_MODE,"result":res}), 200
    except Exception as e:
        logging.exception("trade error")
        return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
