from coinbase.rest import RESTClient
import uuid, time
from google.cloud import secretmanager

# Function to access secrets
def _secret(name:str)->str:
    _sec = secretmanager.SecretManagerServiceClient()
    return _sec.access_secret_version(
        request={"name": f"projects/tvcb-prod/secrets/{name}/versions/latest"}
    ).payload.data.decode()

# Fill these from your Coinbase Advanced API key (org-based)
ORG_ID = "organizations/cb7f9643-eff7-40c5-acac-364e929aca44"
KEY_ID = _secret("coinbase-name")
PRIVATE_KEY_PEM = _secret("coinbase-api-secret")

client = RESTClient(api_key=f"{ORG_ID}/apiKeys/{KEY_ID}", private_key=PRIVATE_KEY_PEM)

# 1) list a product to confirm auth & connectivity
products = client.get_products(limit=1)
print("products_ok", bool(products))

# 2) place a tiny $1 market BUY on SOL-USD
client_order_id = str(uuid.uuid4())
resp = client.create_order(
    client_order_id=client_order_id,
    product_id="SOL-USD",
    side="BUY",
    order_configuration={"market_market_ioc":{"quote_size":"1.00"}}
)
print("buy_resp", resp)

order_id = resp.get("success_response", {}).get("order_id")
time.sleep(2)

# 3) fetch recent fills to confirm execution
fills = client.list_fills(product_id="SOL-USD", limit=10)
print("fills", fills)

# 4) (optional) place a tiny market SELL for ~$1 notional if you hold SOL
client_order_id = str(uuid.uuid4())
sell = client.create_order(
    client_order_id=client_order_id,
    product_id="SOL-USD",
    side="SELL",
    order_configuration={"market_market_ioc":{"quote_size":"1.00"}}
)
print("sell_resp", sell)