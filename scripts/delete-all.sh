#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OutageShield AI — DELETE EVERYTHING
# Run this after the demo to remove all AWS resources.
# ─────────────────────────────────────────────────────────────────────────────

REGION="us-east-1"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  OutageShield AI — DELETING ALL RESOURCES"
echo "════════════════════════════════════════════════════════════════"
echo ""

# 1. Remove EventBridge rule (demo auto-trigger)
echo "[1/12] Removing EventBridge alarm-to-detection rule..."
aws events remove-targets --rule outageshield-alarm-to-detection-dev --ids DetectionLambda --region $REGION 2>/dev/null
aws events delete-rule --name outageshield-alarm-to-detection-dev --region $REGION 2>/dev/null
echo "  ✓ Done"

# 2. Delete CloudFormation stacks (reverse order)
echo "[2/12] Deleting WebSocket stack..."
aws cloudformation delete-stack --stack-name outageshield-websocket-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-websocket-dev --region $REGION 2>/dev/null

echo "[3/12] Deleting Auth stack..."
aws cloudformation delete-stack --stack-name outageshield-auth-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-auth-dev --region $REGION 2>/dev/null

echo "[4/12] Deleting Dashboard stack..."
aws cloudformation delete-stack --stack-name outageshield-dashboard-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-dashboard-dev --region $REGION 2>/dev/null

echo "[5/12] Deleting Remediation stack..."
aws cloudformation delete-stack --stack-name outageshield-remediation-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-remediation-dev --region $REGION 2>/dev/null

echo "[6/12] Deleting Orchestration stack..."
aws cloudformation delete-stack --stack-name outageshield-orchestration-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-orchestration-dev --region $REGION 2>/dev/null

echo "[7/12] Deleting Reasoning stack..."
aws cloudformation delete-stack --stack-name outageshield-reasoning-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-reasoning-dev --region $REGION 2>/dev/null

echo "[8/12] Deleting Correlation stack..."
aws cloudformation delete-stack --stack-name outageshield-correlation-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-correlation-dev --region $REGION 2>/dev/null

echo "[9/12] Deleting Detection stack..."
aws cloudformation delete-stack --stack-name outageshield-detection-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-detection-dev --region $REGION 2>/dev/null

echo "[10/12] Deleting Ingestion stack..."
aws cloudformation delete-stack --stack-name outageshield-ingestion-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-ingestion-dev --region $REGION 2>/dev/null

echo "[11/12] Deleting Notifications stack..."
aws cloudformation delete-stack --stack-name outageshield-notifications-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-notifications-dev --region $REGION 2>/dev/null

echo "[12/12] Deleting Storage stack (DynamoDB + OpenSearch)..."
aws cloudformation delete-stack --stack-name outageshield-storage-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name outageshield-storage-dev --region $REGION 2>/dev/null

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ ALL RESOURCES DELETED"
echo "════════════════════════════════════════════════════════════════"
echo ""
