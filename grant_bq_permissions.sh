#!/usr/bin/env bash
PROJECT_ID=tvcb-prod
DATASET=trading

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
PUBSUB_AGENT="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

# Grant on the dataset (applies to all tables in it)
bq add-iam-policy-binding \
  --member="$PUBSUB_AGENT" \
  --role="roles/bigquery.dataEditor" \
  "$PROJECT_ID:$DATASET"

bq add-iam-policy-binding \
  --member="$PUBSUB_AGENT" \
  --role="roles/bigquery.metadataViewer" \
  "$PROJECT_ID:$DATASET"