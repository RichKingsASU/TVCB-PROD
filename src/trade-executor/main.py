# src/trade-executor/main.py
import base64, json, logging, os, uuid
from fastapi import FastAPI, Request, Response, HTTPException
from google.cloud import secretmanager, bigquery
import google.cloud.logging
from coinbase_client import CoinbaseAdvClient

client = google.cloud.logging.Client()
client.setup_logging()

log = logging.getLogger("trade-executor")

app = FastAPI()

PROJECT_ID = os.environ.get("PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT"))
TRADING_MODE = os.environ.get("TRADING_MODE", "PREVIEW").upper()  # PREVIEW or LIVE
USD_PER_TRADE = float(os.environ.get("USD_PER_TRADE", "1"))
COINBASE_ORG_ID = os.environ.get("COINBASE_ORG_ID")

# Secrets
def _secret(name:str)->str:
    _sec = secretmanager.SecretManagerServiceClient()
    return _sec.access_secret_version(
        request={"name": f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"}
    ).payload.data.decode()

if not COINBASE_ORG_ID:
    raise ValueError("COINBASE_ORG_ID environment variable not set")

api_key_id = _secret("coinbase-org-id")
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
    logging.info(f"Converted symbol {symbol} to product_id {product_id}")
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

    if order and order.get("success"):
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
        logging.error(f"CB ORDER ERR: {order.get('error_response') if order else 'Order is None'}")

def _decode_wrapped(body: dict):
    """Decode Pub/Sub WRAPPED payload -> dict or text."""
    try:
        b64 = body["message"]["data"]
        data = base64.b64decode(b64 or b"")
        try:
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            return {"text": data.decode("utf-8", errors="replace")}
    except KeyError as e:
        raise HTTPException(400, f"Malformed Pub/Sub wrapped body: missing {e}")


@app.post("/pubsub")
async def pubsub(request: Request):
    raw = await request.body()

    # Try to parse as JSON first
    event = None
    try:
        body = json.loads(raw)
        # WRAPPED? (default push format)
        if isinstance(body, dict) and "message" in body and isinstance(body["message"], dict) and "data" in body["message"]:
            event = _decode_wrapped(body)
        else:
            # UNWRAPPED JSON
            event = body
    except Exception:
        # UNWRAPPED non-JSON: treat as text
        event = {"text": raw.decode("utf-8", errors="replace")}

    # Optional: capture Pub/Sub metadata headers when write-metadata is enabled
    meta = {
        "subscription": request.headers.get("x-goog-pubsub-subscription-name"),
        "message_id": request.headers.get("x-goog-pubsub-message-id"),
        "publish_time": request.headers.get("x-goog-pubsub-publish-time"),
        "ordering_key": request.headers.get("x-goog-pubsub-ordering-key"),
        "content_type": request.headers.get("content-type"),
    }

    # Structured log (lands in jsonPayload in Cloud Logging)
    # Requires google-cloud-logging stdlib integration OR you can just log a JSON-string.
    log.info("PubSub event", extra={"json_fields": {"event": event, "meta": meta}})

    # Idempotency check
    alert_id = event.get("alert_id")
    if alert_id:
        bq_client = bigquery.Client()
        query = f"""SELECT alert_id FROM `tvcb-prod.trading.seen_alerts` WHERE alert_id = '{alert_id}'"""
        query_job = bq_client.query(query)
        results = query_job.result()
        if results.total_rows > 0:
            log.info(f"Duplicate alert_id: {alert_id}. Skipping.")
            return Response(status_code=204)

    try:
        place_trade(event)
    except (ValueError, KeyError) as e:
        log.error(f"Failed to process event: {e}")
        raise HTTPException(400, f"Invalid trade signal: {e}")
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(500, "Internal Server Error")

    # Mark alert as seen
    if alert_id:
        rows_to_insert = [{u"alert_id": alert_id}]
        errors = bq_client.insert_rows_json("tvcb-prod.trading.seen_alerts", rows_to_insert)
        if errors == []:
            log.info(f"Inserted alert_id: {alert_id} into seen_alerts table.")
        else:
            log.error(f"Encountered errors while inserting rows: {errors}")

    # ACK quickly with no body
    return Response(status_code=204)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    try:
        # Check Secret Manager connectivity
        _secret("coinbase-org-id")
        # Check Coinbase API connectivity
        cb.get_accounts()
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Readiness check failed: {e}")
        raise HTTPException(503, "Service Unavailable")