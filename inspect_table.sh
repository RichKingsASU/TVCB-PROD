#!/usr/bin/env bash
PROJECT_ID=tvcb-prod
DATASET=trading
TABLE=alerts_raw

# list tables
bq ls -t ${PROJECT_ID}:${DATASET}

# inspect table metadata & schema
bq show --format=prettyjson ${PROJECT_ID}:${DATASET}.${TABLE} | jq '.schema'
