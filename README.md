# TVCB-PROD (TradingView → Cloud Run → Pub/Sub → Coinbase)

Production-ready scaffold:
- Cloud Run services: webhook-handler, trade-executor
- Pub/Sub topic: trading-signals (+ DLQ)
- Secret Manager: trading/webhook secret, Coinbase API key/secret
- Cloud Build CI/CD: builds images, deploys to Cloud Run
