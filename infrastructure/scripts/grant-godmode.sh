#!/usr/bin/env bash
# Time-boxed "break-glass" admin (expires in ~4h). Use only to bootstrap infra.
set -euo pipefail
ORG_ID="$1"; BILLING_ID="$2"; GROUP_EMAIL="$3"
EXPIRY=$(date -u -d "+4 hours" +"%Y-%m-%dT%H:%M:%SZ")
COND="--condition=expression="request.time < timestamp('${EXPIRY}')",title="TimeBound",description="Expires ${EXPIRY}""
for ROLE in roles/resourcemanager.organizationAdmin roles/resourcemanager.folderAdmin roles/resourcemanager.projectCreator roles/iam.securityAdmin roles/iam.organizationRoleAdmin roles/iam.roleAdmin roles/iam.serviceAccountAdmin roles/iam.serviceAccountKeyAdmin roles/serviceusage.serviceUsageAdmin roles/orgpolicy.policyAdmin roles/logging.admin roles/monitoring.admin ; do
  gcloud organizations add-iam-policy-binding "$ORG_ID" --member="group:${GROUP_EMAIL}" --role="$ROLE" $COND
done
gcloud beta billing accounts add-iam-policy-binding "$BILLING_ID" --member="group:${GROUP_EMAIL}" --role="roles/billing.admin"
echo "[ok] Granted temporary elevated access to $GROUP_EMAIL until $EXPIRY"
