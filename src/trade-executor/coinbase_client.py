# src/trade-executor/coinbase_client.py
import math, uuid, logging
from coinbase.rest import RESTClient

class CoinbaseAdvClient:
    def __init__(self, api_key:str, api_secret:str, base_url:str="api.coinbase.com"):
        # Works with Advanced Trade API keys (API key id + API private key)
        self.rest = RESTClient(api_key=api_key, api_secret=api_secret, base_url=base_url)

    def _best_prices(self, product_id:str) -> tuple[float,float]:
        # Use best bid/ask to compute base_size for sells
        book = self.rest.get_best_bid_ask(product_ids=[product_id])
        pb = book["pricebooks"][0]
        best_bid = float(pb["bids"][0]["price"])
        best_ask = float(pb["asks"][0]["price"])
        return best_bid, best_ask

    def _round_base(self, product_id:str, base_size:float) -> float:
        # Respect base increment from product meta
        prod = self.rest.get_product(product_id)
        inc = float(prod["product"]["base_increment"])
        return math.floor(base_size / inc) * inc

    def buy_usd(self, product_id:str, usd:float, client_order_id:str|None=None, preview:bool=False):
        prod = self.rest.get_product(product_id)
        min_size = float(prod["product"]["quote_min_size"])
        if usd < min_size:
            logging.warning(f"Trade amount ${usd:.2f} is below product minimum ${min_size:.2f} for {product_id}. Bumping to minimum.")
            usd = min_size

        client_order_id = client_order_id or str(uuid.uuid4())
        if preview:
            return self.rest.preview_market_order_buy(product_id=product_id, quote_size=f"{usd:.2f}")
        return self.rest.market_order_buy(client_order_id=client_order_id, product_id=product_id, quote_size=f"{usd:.2f}")

    def sell_usd(self, product_id:str, usd:float, client_order_id:str|None=None, preview:bool=False):
        client_order_id = client_order_id or str(uuid.uuid4())
        best_bid, _ = self._best_prices(product_id)
        raw_base = usd / best_bid
        base_size = self._round_base(product_id, raw_base)
        if base_size <= 0:
            raise ValueError("Computed base_size below min increment")
        if preview:
            return self.rest.preview_market_order_sell(product_id=product_id, base_size=f"{base_size:.12f}")
        return self.rest.market_order_sell(client_order_id=client_order_id, product_id=product_id, base_size=f"{base_size:.12f}")

    def get_order(self, order_id:str):
        return self.rest.get_order(order_id=order_id)