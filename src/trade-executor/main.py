import os, json, uuid, logging
from flask import Flask, request, jsonify
from coinbase.rest import RESTClient

# Cloud Run env (injected from Secret Manager)
API_KEY_NAME   = os.environ["COINBASE_NAME"]        # organizations/{org_id}/apiKeys/{key_id}
API_PRIVATEKEY = os.environ["COINBASE_PRIVATEKEY"]  # -----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n
TRADING_MODE   = os.getenv("TRADING_MODE", "DRY_RUN").upper()
USD_PER_TRADE  = float(os.getenv("USD_PER_TRADE", "1"))
PRODUCT_FALLBACK = os.getenv("PRODUCT_FALLBACK", "BTC-USD")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Coinbase Advanced Trade REST client (JWT ES256 under the hood)
# Auth model: org API key path + PEM private key (JWT), per Coinbase docs. :contentReference[oaicite:1]{index=1}
cb = RESTClient(api_key=API_KEY_NAME, api_secret=API_PRIVATEKEY)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "mode": TRADING_MODE}), 200

@app.post("/pubsub")
def handle_pubsub():
    # Pub/Sub push body shape: {"message":{"data": base64json, "attributes":{...}}, "subscription": "..."}
    # Push is OIDC-authenticated (invoker SA). :contentReference[oaicite:2]{index=2}
    envelope = request.get_json(force=True, silent=True) or {}
    msg = envelope.get("message", {})
    if "data" not in msg:
        return ("", 204)

    import base64
    payload = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
    symbol  = payload.get("symbol") or PRODUCT_FALLBACK   # e.g., "BTCUSD" or "BTC-USD"
    action  = (payload.get("action") or "").lower()
    price   = payload.get("price")
    ts      = payload.get("timestamp") or payload.get("ts")

    # Normalize product_id
    product_id = symbol if "-" in symbol else f"{symbol[:3]}-{symbol[3:]}" if len(symbol) == 6 else f"{symbol}-USD"

    # Idempotent client order id (safe even if re-delivered)
    coid = f"tvcb-{product_id}-{str(ts).replace(':','').replace('.','')}-{msg.get('messageId','noid')}"

    logging.info(f"Signal: {action} ${USD_PER_TRADE} on {product_id} (mode={TRADING_MODE})")

    if action not in ("buy", "sell"):
        logging.warning("Ignoring non-trade action")
        return ("", 204)

    try:
        if TRADING_MODE != "LIVE":
            # Preview shows exact reason if order would fail (min notional, perms, etc.). :contentReference[oaicite:3]{index=3}
            if action == "buy":
                pv = cb.preview_market_order_buy(product_id=product_id, quote_size=str(USD_PER_TRADE))
            else:
                pv = cb.preview_market_order_sell(product_id=product_id, base_size=payload.get("size","0.001"))
            logging.info(f"PREVIEW: {json.dumps(dict(pv), separators=(',',':'))}")
            return ("", 204)

        # LIVE mode — place market order ($)
        if action == "buy":
            res = cb.market_order_buy(client_order_id=coid, product_id=product_id, quote_size=str(USD_PER_TRADE))
        else:
            # For sells you normally specify size in base currency; if not present, you could query accounts.
            res = cb.market_order_sell(client_order_id=coid, product_id=product_id, base_size=payload.get("size","0.001"))
        logging.info(f"ORDER: {json.dumps(dict(res), separators=(',',':'))}")
        return ("", 204)
    except Exception as e:
        logging.exception(f"Trade error: {e}")
        # Return 500 so Pub/Sub can retry and/or route to DLQ you configured.
        return ("", 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
