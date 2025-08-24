Use the service URL from Cloud Run: https://<svc>-<hash>-<region>.run.app/webhook/tradingview
Add HTTP header "X-TV-Secret: <your secret>" in TradingView alert setup.
Body suggestion:
{"symbol":"BTC-USD","action":"buy","strategy":"ma-x","note":"tv-alert"}
