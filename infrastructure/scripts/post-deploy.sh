#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1

# Create authenticated push subscription to Cloud Run trade-executor
EXEC_URL=$(gcloud run services describe trade-executor --region=$REGION --format='value(status.url)')
gcloud pubsub subscriptions create trading-signals-sub   --topic=trading-signals   --push-endpoint="${EXEC_URL}/pubsub"   --push-auth-service-account="ts-executor-sa @${PROJECT_ID}.iam.gserviceaccount.com"   --dead-letter-topic=projects/${PROJECT_ID}/topics/trading-signals-dlq   --max-delivery-attempts=5 || true
echo "[ok] Pub/Sub push subscription configured."
