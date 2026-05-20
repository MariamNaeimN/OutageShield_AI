#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OutageShield AI - Stack Deployment Script
# Deploys all CloudFormation stacks in dependency order.
# ─────────────────────────────────────────────────────────────────────────────

set -e

ENVIRONMENT=${1:-dev}
REGION=${2:-us-east-1}
STACK_PREFIX="outageshield"

echo "═══════════════════════════════════════════════════════════════"
echo "  OutageShield AI - Deploying to: ${ENVIRONMENT} (${REGION})"
echo "═══════════════════════════════════════════════════════════════"

deploy_stack() {
    local stack_name="${STACK_PREFIX}-${1}-${ENVIRONMENT}"
    local template_file="$2"
    local params="$3"

    echo ""
    echo "──────────────────────────────────────────────────────────────"
    echo "  Deploying: ${stack_name}"
    echo "  Template:  ${template_file}"
    echo "──────────────────────────────────────────────────────────────"

    aws cloudformation deploy \
        --stack-name "${stack_name}" \
        --template-file "${template_file}" \
        --parameter-overrides Environment="${ENVIRONMENT}" ${params} \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${REGION}" \
        --no-fail-on-empty-changeset

    echo "  ✓ ${stack_name} deployed successfully"
}

# ─────────────────────────────────────────────────────────────────────────────
# Deploy Order (respects cross-stack dependencies)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "Stack deployment order:"
echo "  1. Storage (DynamoDB + OpenSearch)"
echo "  2. Notifications (SNS + Ticket Integrator)"
echo "  3. Ingestion (EventBridge + Lambda)"
echo "  4. Detection (Anomaly detection + Signal generation)"
echo "  5. Correlation (Context building)"
echo "  6. Reasoning (Bedrock Agent + Root Cause + Remediation)"
echo "  7. Orchestration (Step Functions)"
echo "  8. Remediation (Systems Manager execution)"
echo "  9. Dashboard (API Gateway + Lambda)"
echo ""

# 1. Storage — no dependencies
deploy_stack "storage" "02-storage-stack.yaml"

# 2. Notifications — depends on storage
deploy_stack "notifications" "07-notifications-stack.yaml"

# 3. Ingestion — depends on storage, notifications
deploy_stack "ingestion" "01-ingestion-stack.yaml"

# 4. Detection — depends on storage
deploy_stack "detection" "03-detection-stack.yaml"

# 5. Correlation — depends on storage
deploy_stack "correlation" "04-correlation-stack.yaml"

# 6. Reasoning — depends on storage
deploy_stack "reasoning" "05-reasoning-stack.yaml"

# 7. Orchestration — depends on correlation, reasoning, notifications
deploy_stack "orchestration" "06-orchestration-stack.yaml"

# 8. Remediation — depends on storage, notifications
deploy_stack "remediation" "08-remediation-stack.yaml"

# 9. Dashboard — depends on storage
deploy_stack "dashboard" "09-dashboard-stack.yaml"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ All stacks deployed successfully!"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Print outputs
echo "Key Endpoints:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_PREFIX}-dashboard-${ENVIRONMENT}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" \
    --output text 2>/dev/null && echo "" || echo "  (Dashboard URL will be available after deployment)"
