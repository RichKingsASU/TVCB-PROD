#!/usr/bin/env bash
LOCATION=US
DATASET=trading
RAW_TABLE=alerts_raw
PROJECT_ID=tvcb-prod

# Create dataset (once)
bq --location=$LOCATION --project_id=$PROJECT_ID mk -d --description "Trading alerts (raw)" $DATASET

# Create raw table with columns Pub/Sub can populate easily
bq mk --table $PROJECT_ID:$DATASET.$RAW_TABLE \
  data:JSON,subscription_name:STRING,message_id:STRING,publish_time:TIMESTAMP,attributes:JSON
