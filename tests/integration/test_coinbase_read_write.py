import os
from coinbase.rest import RESTClient

def test_key_permissions():
    c = RESTClient()
    perms = c.get_api_key_permissions()
    assert isinstance(perms, dict)

def test_preview_order_buy():
    c = RESTClient()
    res = c.preview_market_order_buy(product_id="BTC-USD", quote_size="1")
    assert "order_configuration" in res
