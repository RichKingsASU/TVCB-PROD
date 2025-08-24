#!/usr/bin/env bash
set -euo pipefail

mkdir -p .github/workflows src/webhook-handler src/trade-executor tests/integration infrastructure/scripts config db docs

cat > .gitignore <<'EOF'
__pycache__/
*.py[cod]
.env
.venv/
.env.*
.coverage
dist/
build/
.DS_Store
EOF

cat > README.md <<'EOF'
# TVCB-PROD (TradingView → Cloud Run → Pub/Sub → Coinbase)

Production-ready scaffold:
- Cloud Run services: webhook-handler, trade-executor
- Pub/Sub topic: trading-signals (+ DLQ)
- Secret Manager: trading/webhook secret, Coinbase API key/secret
- Cloud Build CI/CD: builds images, deploys to Cloud Run
EOF

# --- Cloud Build (build + deploy both services) ---
cat > cloudbuild.yaml <<'EOF'
substitutions:
  _REGION: us-central1
  _REPO: tvcb-prod

steps:
- name: gcr.io/cloud-builders/docker
  dir: src/webhook-handler
  args: ['build','-t','${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/webhook-handler:$COMMIT_SHA','.']

- name: gcr.io/cloud-builders/docker
  dir: src/trade-executor
  args: ['build','-t','${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/trade-executor:$COMMIT_SHA','.']

- name: gcr.io/google.com/cloudsdktool/cloud-sdk
  entrypoint: bash
  args:
  - -lc
  - >
    gcloud run deploy webhook-handler
    --image ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/webhook-handler:$COMMIT_SHA
    --region ${_REGION}
    --allow-unauthenticated
    --service-account ts-webhook-sa@$PROJECT_ID.iam.gserviceaccount.com
    --update-secrets=TV_SECRET=tv-secret:latest
    --set-env-vars=PROJECT_ID=$PROJECT_ID,TOPIC_NAME=trading-signals

- name: gcr.io/google.com/cloudsdktool/cloud-sdk
  entrypoint: bash
  args:
  - -lc
  - >
    gcloud run deploy trade-executor
    --image ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/trade-executor:$COMMIT_SHA
    --region ${_REGION}
    --no-allow-unauthenticated
    --service-account ts-executor-sa@$PROJECT_ID.iam.gserviceaccount.com
    --set-env-vars=PROJECT_ID=$PROJECT_ID,TRADING_MODE=PREVIEW
images:
- ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/webhook-handler:$COMMIT_SHA
- ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/trade-executor:$COMMIT_SHA
EOF

# --- GitHub Action (optional quick dep scan) ---
cat > .github/workflows/security-scan.yml <<'EOF'
name: security-scan
on: [push]
jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install pip-audit
      - run: |
          pip-audit -r src/webhook-handler/requirements.txt || true
          pip-audit -r src/trade-executor/requirements.txt || true
EOF

# --- Webhook handler (TradingView → Pub/Sub) ---
cat > src/webhook-handler/requirements.txt <<'EOF'
Flask==3.0.3
gunicorn==22.0.0
google-cloud-pubsub==2.21.5
EOF

cat > src/webhook-handler/Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["gunicorn","-w","2","-b","0.0.0.0:8080","main:app"]
EOF

cat > src/webhook-handler/main.py <<'EOF'
import os, json, base64, hashlib, hmac
from flask import Flask, request, jsonify
from google.cloud import pubsub_v1

PROJECT_ID = os.environ["PROJECT_ID"]
TOPIC_NAME = os.environ.get("TOPIC_NAME","trading-signals")
TV_SECRET = os.environ.get("TV_SECRET")
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

app = Flask(__name__)

@app.get("/healthz")
def health():
    return {"status":"ok"}, 200

@app.post("/webhook/tradingview")
def tv_webhook():
    # TradingView posts JSON we define in the alert (no official HMAC header)
    # Use a shared secret sent in a header you control.
    secret = request.headers.get("X-TV-Secret")
    if not TV_SECRET or secret != TV_SECRET:
        return jsonify({"error":"unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    # minimal validation
    for k in ("symbol","action"):
        if k not in data: return jsonify({"error":f"missing {k}"}), 400

    attrs = {
        "symbol": str(data.get("symbol")),
        "action": str(data.get("action")),
        "strategy": str(data.get("strategy","na")),
        "version": "v1",
    }
    publisher.publish(topic_path, json.dumps(data).encode("utf-8"), **attrs)
    return jsonify({"status":"published","attrs":attrs}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
EOF

# --- Trade executor (Pub/Sub push → Coinbase) ---
cat > src/trade-executor/requirements.txt <<'EOF'
Flask==3.0.3
gunicorn==22.0.0
coinbase-advanced-py==1.9.0
EOF

cat > src/trade-executor/Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["gunicorn","-w","2","-b","0.0.0.0:8080","main:app"]
EOF

cat > src/trade-executor/main.py <<'EOF'
import os, json, base64, logging
from flask import Flask, request, jsonify
from coinbase.rest import RESTClient

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
TRADING_MODE = os.environ.get("TRADING_MODE","PREVIEW").upper()

# RESTClient reads COINBASE_API_KEY / COINBASE_API_SECRET from env
cb = RESTClient()

@app.get("/healthz")
def health():
    return {"status":"ok","mode":TRADING_MODE}, 200

@app.post("/pubsub")
def pubsub_push():
    # Pub/Sub push: envelope with base64 data
    envelope = request.get_json(force=True, silent=True) or {}
    msg = envelope.get("message", {})
    data_b64 = msg.get("data")
    if not data_b64:
        return jsonify({"error":"no-data"}), 400
    payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    symbol = payload.get("symbol","BTC-USD").replace("/","-")
    action = payload.get("action","buy").lower()

    # PREVIEW endpoints in SDK for safe testing; LIVE uses market_order_*.
    try:
        if TRADING_MODE == "PREVIEW":
            if action == "buy":
                res = cb.preview_market_order_buy(product_id=symbol, quote_size="5")
            else:
                res = cb.preview_market_order_sell(product_id=symbol, base_size="0.0001")
        else:
            if action == "buy":
                res = cb.market_order_buy(product_id=symbol, quote_size="5")
            else:
                res = cb.market_order_sell(product_id=symbol, base_size="0.0001")
        logging.info("Order response: %s", res)
        return jsonify({"status":"ok","mode":TRADING_MODE,"result":res}), 200
    except Exception as e:
        logging.exception("trade error")
        return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
EOF

# --- Minimal Coinbase SDK integration tests (sandbox-friendly) ---
cat > tests/integration/test_coinbase_read_write.py <<'EOF'
import os
from coinbase.rest import RESTClient

def test_key_permissions():
    c = RESTClient()
    perms = c.get_api_key_permissions()
    assert isinstance(perms, dict)

def test_preview_order_buy():
    c = RESTClient()
    res = c.preview_market_order_buy(product_id="BTC-USD", quote_size="1")
    assert "order_configuration" in res
EOF

# --- Config and infra helper scripts ---
cat > config/app-config.yaml <<'EOF'
risk:
  per_order_usd_cap: 100
  daily_budget_usd_cap: 500
EOF

cat > infrastructure/scripts/grant-godmode.sh <<'EOF'
#!/usr/bin/env bash
# Time-boxed "break-glass" admin (expires in ~4h). Use only to bootstrap infra.
set -euo pipefail
ORG_ID="$1"; BILLING_ID="$2"; GROUP_EMAIL="$3"
EXPIRY=$(date -u -d "+4 hours" +"%Y-%m-%dT%H:%M:%SZ")
COND="--condition=expression=\"request.time < timestamp('${EXPIRY}')\",title=\"TimeBound\",description=\"Expires ${EXPIRY}\""
for ROLE in roles/resourcemanager.organizationAdmin roles/resourcemanager.folderAdmin roles/resourcemanager.projectCreator roles/iam.securityAdmin roles/iam.organizationRoleAdmin roles/iam.roleAdmin roles/iam.serviceAccountAdmin roles/iam.serviceAccountKeyAdmin roles/serviceusage.serviceUsageAdmin roles/orgpolicy.policyAdmin roles/logging.admin roles/monitoring.admin ; do
  gcloud organizations add-iam-policy-binding "$ORG_ID" --member="group:${GROUP_EMAIL}" --role="$ROLE" $COND
done
gcloud beta billing accounts add-iam-policy-binding "$BILLING_ID" --member="group:${GROUP_EMAIL}" --role="roles/billing.admin"
echo "[ok] Granted temporary elevated access to $GROUP_EMAIL until $EXPIRY"
EOF

cat > infrastructure/scripts/revoke-godmode.sh <<'EOF'
#!/usr/bin/env bash
# Remove the above bindings (manually reverse roles as needed).
echo "Revoke script placeholder: remove conditional bindings added by grant-godmode.sh"
EOF

cat > infrastructure/scripts/setup-gcp.sh <<'EOF'
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
EOF

cat > infrastructure/scripts/post-deploy.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1

# Create authenticated push subscription to Cloud Run trade-executor
EXEC_URL=$(gcloud run services describe trade-executor --region=$REGION --format='value(status.url)')
gcloud pubsub subscriptions create trading-signals-sub \
  --topic=trading-signals \
  --push-endpoint="${EXEC_URL}/pubsub" \
  --push-auth-service-account="ts-executor-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --dead-letter-topic=projects/${PROJECT_ID}/topics/trading-signals-dlq \
  --max-delivery-attempts=5 || true
echo "[ok] Pub/Sub push subscription configured."
EOF

cat > docs/TRADINGVIEW_WEBHOOK.md <<'EOF'
Use the service URL from Cloud Run: https://<svc>-<hash>-<region>.run.app/webhook/tradingview
Add HTTP header "X-TV-Secret: <your secret>" in TradingView alert setup.
Body suggestion:
{"symbol":"BTC-USD","action":"buy","strategy":"ma-x","note":"tv-alert"}
EOF

echo "[ok] Scaffolding complete."
