#!/usr/bin/env bash
set -euo pipefail

### ======= CONFIG =======
PROJECT_ID="tvcb-prod"
REGION="us-central1"
LOCATION="US"

TOPIC="trading-signals"
SUB_BQ="signals-to-bq"

DATASET="trading"
RAW_TABLE="alerts_raw"
VIEW_NAME="alerts_vw"
FACT_TABLE="alerts_fact"

SCHEDULE_ENABLED="true"        # set "false" to skip scheduled query
SCHEDULE_SPEC="every 1 hour"   # e.g., "every 1 hour", "every day 02:00"
SCHEDULE_DISPLAY="alerts_fact_refresh"
### =======================

gcloud config set project "$PROJECT_ID" >/dev/null

echo ">> Enabling required APIs (Pub/Sub, BigQuery, Storage Write, Data Transfer for schedules)..."
gcloud services enable \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  bigquerystorage.googleapis.com \
  bigquerydatatransfer.googleapis.com >/dev/null

echo ">> Ensuring dataset exists: ${PROJECT_ID}:${DATASET}"
bq --location="$LOCATION" mk -d --description "Trading analytics" "${PROJECT_ID}:${DATASET}" 2>/dev/null || true

echo ">> Ensuring raw table exists with 'data' JSON column (required for BQ subscription when not mapping schema)..."
bq query --use_legacy_sql=false --quiet \
"CREATE TABLE IF NOT EXISTS 
${PROJECT_ID}.${DATASET}.${RAW_TABLE}
 (data JSON);"

echo ">> Ensuring Write-Metadata columns exist (subscription_name, message_id, publish_time, attributes)..."
bq query --use_legacy_sql=false --quiet \
"ALTER TABLE 
${PROJECT_ID}.${DATASET}.${RAW_TABLE}
  ADD COLUMN IF NOT EXISTS subscription_name STRING,
  ADD COLUMN IF NOT EXISTS message_id STRING,
  ADD COLUMN IF NOT EXISTS publish_time TIMESTAMP,
  ADD COLUMN IF NOT EXISTS attributes JSON;"

echo ">> Creating or updating the BigQuery subscription -> ${PROJECT_ID}.${DATASET}.${RAW_TABLE} (writeMetadata=true)"
# Try to create; if it exists, update in place.
if gcloud pubsub subscriptions describe "$SUB_BQ" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "$SUB_BQ" \
    --bigquery-table="${PROJECT_ID}.${DATASET}.${RAW_TABLE}" \
    --write-metadata
else
  gcloud pubsub subscriptions create "$SUB_BQ" \
    --topic="$TOPIC" \
    --bigquery-table="${PROJECT_ID}.${DATASET}.${RAW_TABLE}" \
    --write-metadata
fi

echo ">> Creating zero-copy view ${PROJECT_ID}.${DATASET}.${VIEW_NAME}"
bq query --use_legacy_sql=false --quiet \
"CREATE VIEW IF NOT EXISTS 
${PROJECT_ID}.${DATASET}.${VIEW_NAME}
 AS
SELECT
  JSON_VALUE(data,'$.alert_id')  AS alert_id,
  JSON_VALUE(data,'$.symbol')    AS symbol,
  JSON_VALUE(data,'$.exchange')  AS exchange,
  JSON_VALUE(data,'$.timeframe') AS timeframe,
  JSON_VALUE(data,'$.indicator') AS indicator,
  JSON_VALUE(data,'$.action')    AS action,
  SAFE_CAST(JSON_VALUE(data,'$.price') AS NUMERIC) AS price,
  TIMESTAMP(JSON_VALUE(data,'$.ts')) AS event_ts,
  publish_time,
  attributes,
  subscription_name,
  message_id
FROM 
${PROJECT_ID}.${DATASET}.${RAW_TABLE}";

echo ">> (Optional) Creating partitioned & clustered fact table ${PROJECT_ID}.${DATASET}.${FACT_TABLE} (if missing)"
bq query --use_legacy_sql=false --quiet \
"CREATE TABLE IF NOT EXISTS 
${PROJECT_ID}.${DATASET}.${FACT_TABLE}
PARTITION BY DATE(event_ts)
CLUSTER BY symbol, action AS
SELECT
  JSON_VALUE(data,'$.alert_id')  AS alert_id,
  JSON_VALUE(data,'$.symbol')    AS symbol,
  JSON_VALUE(data,'$.exchange')  AS exchange,
  JSON_VALUE(data,'$.timeframe') AS timeframe,
  JSON_VALUE(data,'$.indicator') AS indicator,
  JSON_VALUE(data,'$.action')    AS action,
  SAFE_CAST(JSON_VALUE(data,'$.price') AS NUMERIC) AS price,
  TIMESTAMP(JSON_VALUE(data,'$.ts')) AS event_ts,
  publish_time,
  attributes,
  subscription_name,
  message_id
FROM 
${PROJECT_ID}.${DATASET}.${RAW_TABLE}";

if [[ "$SCHEDULE_ENABLED" == "true" ]]; then
  echo "(Optional) Creating scheduled query to refresh ${FACT_TABLE} (${SCHEDULE_SPEC})"
  # Rebuilds the fact table each run; preserves partitioning/clustering defined above.
  bq query \
    --use_legacy_sql=false \
    --display_name="${SCHEDULE_DISPLAY}" \
    --schedule="${SCHEDULE_SPEC}" \
    --destination_table="${PROJECT_ID}:${DATASET}.${FACT_TABLE}" \
    --replace \
"SELECT
  JSON_VALUE(data,'$.alert_id')  AS alert_id,
  JSON_VALUE(data,'$.symbol')    AS symbol,
  JSON_VALUE(data,'$.exchange')  AS exchange,
  JSON_VALUE(data,'$.timeframe') AS timeframe,
  JSON_VALUE(data,'$.indicator') AS indicator,
  JSON_VALUE(data,'$.action')    AS action,
  SAFE_CAST(JSON_VALUE(data,'$.price') AS NUMERIC) AS price,
  TIMESTAMP(JSON_VALUE(data,'$.ts')) AS event_ts,
  publish_time,
  attributes,
  subscription_name,
  message_id
FROM 
${PROJECT_ID}.${DATASET}.${RAW_TABLE}";
fi

echo ">> Done."
echo "   - Subscription: $(gcloud pubsub subscriptions describe "$SUB_BQ" --format='value(name)')"
echo "   - View:         ${PROJECT_ID}.${DATASET}.${VIEW_NAME}"
echo "   - Fact table:   ${PROJECT_ID}.${DATASET}.${FACT_TABLE}"
