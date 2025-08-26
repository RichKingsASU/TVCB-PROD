# src/trade-executor/main.py
import base64, json, logging, os, uuid
from flask import Flask, request
from google.cloud import secretmanager
from coinbase_client import CoinbaseAdvClient

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT"))
TRADING_MODE = os.environ.get("TRADING_MODE", "PREVIEW").upper()  # PREVIEW or LIVE
USD_PER_TRADE = float(os.environ.get("USD_PER_TRADE", "1"))
COINBASE_ORG_ID = os.environ.get("COINBASE_ORG_ID")

# Secrets
_sec = secretmanager.SecretManagerServiceClient()
def _secret(name:str)->str:
    return _sec.access_secret_version(
        request={"name": f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"}
    ).payload.data.decode()

if not COINBASE_ORG_ID:
    raise ValueError("COINBASE_ORG_ID environment variable not set")

api_key_id = _secret("coinbase-api-key-id")
api_key    = f"organizations/{COINBASE_ORG_ID}/apiKeys/{api_key_id}"
api_secret = _secret("coinbase-api-secret") # Advanced Trade API private key (PEM)
cb = CoinbaseAdvClient(api_key, api_secret)

def to_product_id(symbol:str)->str:
    # BTCUSD -> BTC-USD default, or pass through if already BTC-USD
    return symbol if "-" in symbol else f"{symbol[:3]}-{symbol[3:]}"

def place_trade(signal:dict):
    symbol = signal["symbol"]
    action = signal["action"].lower()
    product_id = to_product_id(symbol)
    usd = float(signal.get("funds", USD_PER_TRADE))  # default $1/trade
    live = (TRADING_MODE == "LIVE")
    logging.info(f"Executing {action} ${usd} on {product_id} (mode={TRADING_MODE})")

    order = None
    if action == "buy":
        order = cb.buy_usd(product_id, usd, preview=not live)
    elif action == "sell":
        order = cb.sell_usd(product_id, usd, preview=not live)
    else:
        raise ValueError(f"Unsupported action: {action}")

    if order.get("success"):
        success_response = order.get('success_response')
        logging.info(f"CB ORDER OK: {success_response}")
        order_id = success_response.get('order_id')
        if order_id:
            try:
                verified_order = cb.get_order(order_id)
                logging.info(f"CB ORDER VERIFIED: {verified_order}")
            except Exception as e:
                logging.error(f"Failed to verify order {order_id}: {e}")

    else:
        logging.error(f"CB ORDER ERR: {order.get('error_response') or order}")


@app.route("/pubsub", methods=["POST"])
def pubsub_push():
    # A 2xx response ACKs the message; non-2xx triggers retry. Keep fast. :contentReference[oaicite:4]{index=4}
    envelope = request.get_json(silent=True) or {}
    msg = envelope.get("message", {})
    data_b64 = msg.get("data")
    if not data_b64:
        return ("no data", 204)
    try:
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
        place_trade(payload)
        return ("", 204)  # any 2xx is OK for Pub/Sub ack :contentReference[oaicite:5]{index=5}
    except Exception as e:
        logging.exception("Trade execution failed")
        # Still 2xx to avoid infinite retries; rely on logs/alerts
        return ("", 204)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200

@app.get("/readyz")
def readyz():
    try:
        # Check Secret Manager connectivity
        _secret("coinbase-api-key-id")
        # Check Coinbase API connectivity
        cb.get_accounts()
        return {"status": "ok"}, 200
    except Exception as e:
        logging.error(f"Readiness check failed: {e}")
        return {"status": "error", "error": str(e)}, 503# --- injected health routes (idempotent) ---
try:
    app
except NameError:
    from flask import Flask
    app = Flask(__name__)
from flask import jsonify
def _reg(rule, view_func, methods=("GET",)):
    for r in app.url_map.iter_rules():
        if r.rule == rule:
            break
    else:
        app.add_url_rule(rule, endpoint=f"__inj_{(rule.strip('/') or 'root').replace('/','_')}",
                         view_func=view_func, methods=list(methods))
_reg("/healthz", lambda: (jsonify(status="ok"), 200))
_reg("/",        lambda: ("ok", 200))
# --- end injected health routes ---
