#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1
REPO=tvcb-prod

gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com logging.googleapis.com monitoring.googleapis.com artifactregistry.googleapis.com

# Artifact Registry for images
gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION || true

# Service accounts
gcloud iam service-accounts create ts-webhook-sa --display-name="TVCB Webhook SA" || true
gcloud iam service-accounts create ts-executor-sa --display-name="TVCB Executor SA" || true

# Pub/Sub: topic + DLQ + push subscription will be created after first deploy
gcloud pubsub topics create trading-signals || true
gcloud pubsub topics create trading-signals-dlq || true

# Secrets (create empty; add versions later)
echo -n "changeme" | gcloud secrets create tv-secret --data-file=- || true
echo -n "changeme" | gcloud secrets create coinbase-api-key --data-file=- || true
echo -n "changeme" | gcloud secrets create coinbase-api-secret --data-file=- || true

echo "[ok] Base services enabled and resources created."
