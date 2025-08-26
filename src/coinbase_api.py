import os, json
from coinbase.rest import RESTClient

def get_coinbase_client():
    """Creates and returns a Coinbase REST client."""
    api_key = os.environ.get("COINBASE_API_KEY")
    api_secret = os.environ.get("COINBASE_API_SECRET")

    if not api_key or not api_secret:
        raise Exception("COINBASE_API_KEY and COINBASE_API_SECRET environment variables not set.")

    return RESTClient(api_key=api_key, api_secret=api_secret)

def list_accounts(client):
    """Lists all of the user's accounts."""
    accounts_response = client.get_accounts()
    return [acc.to_dict() for acc in accounts_response.accounts]

def get_account(client, account_uuid):
    """Gets a single account by its UUID."""
    account = client.get_account(account_uuid)
    return account.to_dict()

def get_best_bid_ask(client, product_ids):
    """Gets the best bid/ask for a list of products."""
    response = client.get_best_bid_ask(product_ids)
    return response

def get_product_book(client, product_id, limit):
    """Gets the product book for a single product."""
    response = client.get_product_book(product_id, limit)
    return response

def list_products(client):
    """Lists all available products."""
    response = client.get_products()
    return response

def get_product(client, product_id):
    """Gets a single product by its ID."""
    response = client.get_product(product_id)
    return response

def get_product_candles(client, product_id, start, end, granularity):
    """Gets product candles for a single product."""
    response = client.get_product_candles(product_id, start, end, granularity)
    return response

def get_market_trades(client, product_id, limit):
    """Gets market trades for a single product."""
    response = client.get_market_trades(product_id, limit)
    return response

def create_order(client, client_order_id, product_id, side, order_configuration):
    """Creates a new order."""
    response = client.create_order(client_order_id, product_id, side, order_configuration)
    return response

def cancel_orders(client, order_ids):
    """Cancels a batch of orders."""
    response = client.cancel_orders(order_ids)
    return response

def list_orders(client):
    """Lists all historical orders."""
    response = client.list_orders()
    return response

def list_fills(client):
    """Lists all historical fills."""
    response = client.list_fills()
    return response

def get_order(client, order_id):
    """Gets a single order by its ID."""
    response = client.get_order(order_id)
    return response

def list_portfolios(client):
    """Lists all portfolios."""
    response = client.get_portfolios()
    return response

def create_portfolio(client, name):
    """Creates a new portfolio."""
    response = client.create_portfolio(name)
    return response

def move_portfolio_funds(client, funds, source_portfolio_uuid, target_portfolio_uuid):
    """Moves funds between portfolios."""
    response = client.move_portfolio_funds(funds, source_portfolio_uuid, target_portfolio_uuid)
    return response

def get_portfolio_breakdown(client, portfolio_uuid):
    """Gets the breakdown of a single portfolio."""
    response = client.get_portfolio_breakdown(portfolio_uuid)
    return response

def delete_portfolio(client, portfolio_uuid):
    """Deletes a single portfolio."""
    response = client.delete_portfolio(portfolio_uuid)
    return response

def edit_portfolio(client, portfolio_uuid, name):
    """Edits a single portfolio."""
    response = client.edit_portfolio(portfolio_uuid, name)
    return response

def get_transaction_summary(client):
    """Gets a summary of all transactions."""
    response = client.get_transaction_summary()
    return response

def get_convert_quote(client, from_account, to_account, amount):
    """Gets a convert quote."""
    response = client.get_convert_quote(from_account, to_account, amount)
    return response

def get_convert_trade(client, trade_id):
    """Gets a convert trade."""
    response = client.get_convert_trade(trade_id)
    return response

def commit_convert_trade(client, trade_id):
    """Commits a convert trade."""
    response = client.commit_convert_trade(trade_id)
    return response

def get_server_time(client):
    """Gets the server time."""
    response = client.get_server_time()
    return response

def list_payment_methods(client):
    """Lists all payment methods."""
    response = client.list_payment_methods()
    return response

def get_payment_method(client, payment_method_id):
    """Gets a single payment method by its ID."""
    response = client.get_payment_method(payment_method_id)
    return response

def get_api_key_permissions(client):
    """Gets the permissions for the current API key."""
    response = client.get_api_key_permissions()
    return response

if __name__ == '__main__':
    # Set the project ID here
    os.environ["PROJECT"] = "tvcb-prod"

    client = get_coinbase_client()

    # Example usage:
    print("--- Listing all accounts ---")
    all_accounts = list_accounts(client)
    print(json.dumps(all_accounts, indent=2))

    # Example: Get a single account (replace with a real UUID from your output)
    if all_accounts:
        first_account_uuid = all_accounts[0]['uuid']
        print(f"--- Getting account {first_account_uuid} ---")
        single_account = get_account(client, first_account_uuid)
        print(json.dumps(single_account, indent=2))

    print("--- Listing all products ---")
    products_response = list_products(client)
    products = [p.to_dict() for p in products_response.products]
    print(json.dumps(products, indent=2))

    # Example: Get a single product
    if products:
        first_product_id = products[0]['product_id']
        print(f"--- Getting product {first_product_id} ---")
        product = get_product(client, first_product_id)
        print(json.dumps(product.to_dict(), indent=2))

    print("--- Listing all orders ---")
    orders_response = list_orders(client)
    orders = [o.to_dict() for o in orders_response.orders]
    print(json.dumps(orders, indent=2))

    print("--- Listing all portfolios ---")
    portfolios_response = list_portfolios(client)
    portfolios = [p.to_dict() for p in portfolios_response.portfolios]
    print(json.dumps(portfolios, indent=2))

    print("--- Get API Key Permissions ---")
    permissions = get_api_key_permissions(client)
    print(json.dumps(permissions, indent=2))