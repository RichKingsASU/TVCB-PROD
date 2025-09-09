#!/usr/bin/env bash
PROJECT_ID=tvcb-prod
TOPIC=trading-signals

# Send a realistic alert to your webhook (adjust URL if different)
curl -sS -X POST "https://webhook-handler-tbbq4rfjiq-uc.a.run.app/" \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"e2e","symbol":"SPY","action":"confirm_sell","price":500,"ts":"2025-09-09T17:30:00Z"}'

# Verify the message hit the topic (temporary pull sub)
gcloud pubsub subscriptions create tmp-read --topic=$TOPIC --project=$PROJECT_ID >/dev/null 2>&1 || true
gcloud pubsub subscriptions pull tmp-read --auto-ack --limit=5 --project=$PROJECT_ID --format=json \
| jq -r '.[].message.data' | base64 -d
gcloud pubsub subscriptions delete tmp-read --project=$PROJECT_ID
