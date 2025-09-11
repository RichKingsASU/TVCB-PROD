#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────
# Config
# ───────────────────────────
PROJECT_ID=tvcb-prod
REGION=us-central1
TOPIC=trading-signals
SUB=signals-to-trade-executor
WEBHOOK=webhook-handler
EXECUTOR=trade-executor

gcloud config set project "$PROJECT_ID" >/dev/null

# ───────────────────────────
# 0) Quick sanity: current revisions & URLs
# ───────────────────────────
echo "▶ Cloud Run revisions:"
for SVC in "$WEBHOOK" "$EXECUTOR"; do
  REV=$(gcloud run services describe "$SVC" --region "$REGION" --format='value(status.latestReadyRevisionName)')
  URL=$(gcloud run services describe "$SVC" --region "$REGION" --format='value(status.url)')
  echo "  - $SVC -> $REV -> $URL"
done

# ───────────────────────────
# 1) Validate executor env & secrets (COINBASE_ORG_ID)
#    (Shows plain envs and secret-backed envs if any)
# ───────────────────────────
echo "▶ trade-executor env vars:"
gcloud run services describe "$EXECUTOR" --region "$REGION" --format='json' \
| jq '.spec.template.spec.containers[0].env // []'

echo "▶ trade-executor secret-backed envs (if any):"
gcloud run services describe "$EXECUTOR" --region "$REGION" --format='json' \
| jq '[.spec.template.spec.containers[0].env[]? | select(.valueFrom!=null)]'

# ───────────────────────────
# 2) Pub/Sub push subscription config (wrapped vs unwrapped, auth SA)
# ───────────────────────────
echo "▶ Push subscription config:"
gcloud pubsub subscriptions describe "$SUB" --format='json' \
| jq '{pushEndpoint:.pushConfig.pushEndpoint, oidcSA:(.pushConfig.oidcToken.serviceAccountEmail//null), noWrapper:(.pushConfig.noWrapper//false)}'

# ───────────────────────────
# 3) Webhook → Pub/Sub smoke (send JSON; pull from a temp sub)
# ───────────────────────────
WEBHOOK_URL=$(gcloud run services describe "$WEBHOOK" --region "$REGION" --format='value(status.url)')

echo "▶ Create temp pull sub & send test message via webhook:"
gcloud pubsub subscriptions create debug-sub --topic="$TOPIC" 2>/dev/null || true
curl -sS -X POST "$WEBHOOK_URL/" -H "Content-Type: application/json" \
  -d '{"alert_id":"validate","symbol":"SPY","action":"sell","price":500,"ts":"'"$(date -u +%FT%TZ)"'"}' \
| sed -e 's/^/  webhook: /'

echo "▶ Pull (and decode) from temp sub:"
gcloud pubsub subscriptions pull debug-sub --limit=5 --auto-ack --format=json \
| jq -r '.[].message.data' | base64 -d || true
gcloud pubsub subscriptions delete debug-sub -q || true

# ───────────────────────────
# 4) Pub/Sub → trade-executor: verify deliveries in logs
# ───────────────────────────
echo "▶ trade-executor recent POST /pubsub entries (last 10m)"
gcloud logging read \
  'resource.type="cloud_run_revision"
   AND resource.labels.service_name="'$EXECUTOR'"
   AND httpRequest.requestMethod="POST"
   AND timestamp>="'"$(date -u -d "10 minutes ago" +%FT%TZ)"'"' \
  --limit=10 --format='table(timestamp,httpRequest.status,httpRequest.requestUrl)'

# ───────────────────────────
# 5) (Optional) Simulate Pub/Sub push with OIDC directly (WRAPPED body)
#    Use this if SUB is in default/WRAPPED mode.
# ───────────────────────────
EXECUTOR_URL=$(gcloud run services describe "$EXECUTOR" --region "$REGION" --format='value(status.url)')

WRAPPED_JSON=$(cat <<'JSON'
{
  "message": {
    "data": "__B64__"
  },
  "subscription": "manual-test"
}
JSON
)

B64_PAYLOAD=$(printf '{"symbol":"SPY","action":"sell","ts":"%s"}' "$(date -u +%FT%TZ)" | base64 -w0)
WRAPPED_JSON=${WRAPPED_JSON/__B64__/$B64_PAYLOAD}

echo "▶ Simulated WRAPPED push (expects 2xx)"
curl -i -sS -X POST "${EXECUTOR_URL}/pubsub" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token --audiences=${EXECUTOR_URL})" \
  -H "Content-Type: application/json" \
  --data-binary "$WRAPPED_JSON" | sed -n '1,5p'

# ───────────────────────────
# 6) (Optional) If SUB is UNWRAPPED, simulate raw JSON push instead
# ───────────────────────────
RAW_JSON=$(printf '{"symbol":"SPY","action":"sell","ts":"%s"}' "$(date -u +%FT%TZ)")
echo "▶ Simulated UNWRAPPED push (expects 2xx)"
curl -i -sS -X POST "${EXECUTOR_URL}/pubsub" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token --audiences=${EXECUTOR_URL})" \
  -H "Content-Type: application/json" \
  --data-binary "$RAW_JSON" | sed -n '1,5p'

# ───────────────────────────
# 7) DLQ health (if you attached one)
# ───────────────────────────
if gcloud pubsub topics describe trading-signals-dlq >/dev/null 2>&1; then
  gcloud pubsub subscriptions create trading-signals-dlq-sub --topic=trading-signals-dlq 2>/dev/null || true
  echo "▶ DLQ sample pull (if any messages exist):"
  gcloud pubsub subscriptions pull trading-signals-dlq-sub --limit=5 --auto-ack --format=json \
  | jq -r '.[].message.data' | base64 -d || true
fi

# ───────────────────────────
# 8) Validate min-instances (cold start protection)
#    Prints both v1 (annotation) and v2 (scaling field) locations.
# ───────────────────────────
echo "▶ min-instances setting:"
gcloud run services describe "$EXECUTOR" --region "$REGION" --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/minScale", spec.template.scaling.minInstanceCount)'
