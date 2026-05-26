# Lambda and CloudFormation Stack Alignment

## Summary

This document tracks the alignment between CloudFormation stacks (infrastructure as code) and Lambda deployment scripts (runtime code).

## Lambda Functions and Their Management

| Lambda Function | Stack | Deployment Script | Status |
|----------------|-------|-------------------|--------|
| `outageshield-detection-dev` | 03-detection-stack.yaml | scripts/lambdas/update-detection-opensearch.py | ✅ Aligned |
| `outageshield-correlation-dev` | 04-correlation-stack.yaml | (inline in stack) | ✅ Aligned |
| `outageshield-rootcause-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-rca-lambda-v2.py | ✅ Aligned |
| `outageshield-scoring-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-scoring-lambda.py | ✅ Aligned |
| `outageshield-remediation-recommend-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-remediation-lambda2.py | ✅ Aligned |
| `outageshield-postmortem-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-postmortem-lambda.py | ✅ Aligned |
| `outageshield-remediation-executor-dev` | 08-remediation-stack.yaml | (inline in stack) | ✅ Aligned |
| `outageshield-agent-actions-dev` | 13-bedrock-agent-stack.yaml | scripts/lambdas/add-xray-config-tools.py | ✅ Aligned |
| `outageshield-agent-invoker-dev` | 13-bedrock-agent-stack.yaml | scripts/lambdas/update-agent-invoker.py | ✅ Aligned |
| `outageshield-notification-dev` | 07-notifications-stack.yaml | scripts/lambdas/add-pagerduty-integration.py | ✅ Aligned |
| `outageshield-ticket-dev` | 07-notifications-stack.yaml | (inline in stack) | ✅ Aligned |
| `outageshield-xray-analyzer-dev` | 15-xray-config-stack.yaml | (standalone, not used by workflow) | ℹ️ Standalone |
| `outageshield-config-drift-dev` | 15-xray-config-stack.yaml | (standalone, not used by workflow) | ℹ️ Standalone |

## Key Notes

### Stack vs Script Code Management

The CloudFormation stacks contain **placeholder code** for most Lambdas. The actual runtime code is deployed via Python scripts in `scripts/lambdas/`. This is by design:

1. **Stacks define infrastructure**: IAM roles, permissions, environment variables, log groups
2. **Scripts deploy code**: The actual Lambda function code with business logic

### Deployment Workflow

1. Deploy CloudFormation stacks first (creates Lambda functions with placeholder code)
2. Run deployment scripts to update Lambda code with full implementation

### Recent Updates (May 2026)

1. **Runbook Lookup Fix**: Updated `get_runbook()` in `add-xray-config-tools.py` to:
   - Extract alarm type prefix from alarm names (e.g., `HighLatency` from `HighLatency-prod-api-gateway`)
   - Try multiple matching strategies (exact, prefix, pattern)
   - Support known runbook IDs: HighLatency, High5xxRate, HighCPU, MemoryPressure, ConnectionPool, QueueBacklog, AuthFailures, CacheMissRate, DiskUsage

2. **Agent Actions Lambda**: Now has 6 tools:
   - searchIncidentHistory
   - searchLogs (OpenSearch)
   - getRunbook (with improved matching)
   - checkDeployments
   - searchTraces (X-Ray)
   - checkConfigDrift (AWS Config)

3. **Remediation Lambda**: Pure rule-based logic (no AI hallucination), generates recommendations from 6 sources

## Environment Variables

All Lambdas use these common environment variables:
- `ENVIRONMENT`: dev/staging/prod
- `INCIDENTS_TABLE`: outageshield-incidents-dev
- `EVENTS_TABLE`: outageshield-events-dev
- `RUNBOOKS_TABLE`: outageshield-runbooks-dev
- `DEPLOYMENTS_TABLE`: outageshield-deployments-dev
- `OPENSEARCH_ENDPOINT`: OpenSearch Serverless endpoint

## Step Functions Workflow

The `outageshield-workflow-dev` state machine (06-orchestration-stack.yaml) orchestrates:

1. Step1_Correlate → outageshield-correlation-dev
2. Step2_Score → outageshield-scoring-dev
3. Step3_RootCause → outageshield-rootcause-dev
4. Step3b_AgentInvestigation → outageshield-agent-invoker-dev
5. Step4_Remediation → outageshield-remediation-recommend-dev
6. Step5_CheckApproval → Choice state
7. Step6_Execute → outageshield-remediation-executor-dev (if approved)
8. Step7_CreateTicket → outageshield-ticket-dev
9. Step8_Notify → outageshield-notification-dev
10. Step9_Postmortem → outageshield-postmortem-dev

## DynamoDB Tables

- `outageshield-incidents-dev` - Main incidents table
- `outageshield-events-dev` - Detection events
- `outageshield-runbooks-dev` - Remediation runbooks
- `outageshield-deployments-dev` - Deployment history (with GSI: service-timestamp-index)
- `outageshield-postmortems-dev` - Generated postmortems
