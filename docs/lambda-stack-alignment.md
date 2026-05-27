# Lambda and CloudFormation Stack Alignment

## Summary

This document tracks the alignment between CloudFormation stacks (infrastructure as code) and Lambda deployment scripts (runtime code).

## Lambda Functions and Their Management

| Lambda Function | Stack | Deployment Script | Status |
|----------------|-------|-------------------|--------|
| `outageshield-detection-dev` | 03-detection-stack.yaml | scripts/lambdas/update-detection-opensearch.py | ✅ Aligned |
| `outageshield-correlation-dev` | 04-correlation-stack.yaml | scripts/lambdas/update-correlation-lambda.py | ✅ Aligned |
| `outageshield-rootcause-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-rca-lambda-v2.py | ✅ Aligned |
| `outageshield-scoring-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-scoring-lambda.py | ✅ Aligned |
| `outageshield-remediation-recommend-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-remediation-lambda2.py | ✅ Aligned |
| `outageshield-postmortem-dev` | 05-reasoning-stack.yaml | scripts/lambdas/update-postmortem-lambda.py | ✅ Aligned |
| `outageshield-remediation-summary-dev` | 05-reasoning-stack.yaml | scripts/lambdas/create-summary-lambda.py | ✅ Aligned |
| `outageshield-agent-invoker-dev` | 13-bedrock-agent-stack.yaml | scripts/lambdas/update-agent-invoker.py | ✅ Aligned |
| `outageshield-agent-actions-dev` | 13-bedrock-agent-stack.yaml | scripts/lambdas/update-agent-actions-all-tools.py | ✅ Aligned |
| `outageshield-remediation-executor-dev` | 08-remediation-stack.yaml | (inline in stack) | ✅ Aligned |
| `outageshield-notification-dev` | 07-notifications-stack.yaml | (inline in stack) | ✅ Aligned |
| `outageshield-ticket-dev` | 07-notifications-stack.yaml | (inline in stack) | ✅ Aligned |

## Lambda Scripts Directory

All Lambda deployment scripts are in `scripts/lambdas/`:

```
scripts/lambdas/
├── create-summary-lambda.py          # Summary Lambda with quick actions
├── update-agent-actions-all-tools.py # Agent Actions (6 investigation tools)
├── update-agent-invoker.py           # Agent Invoker (direct tool calls)
├── update-correlation-lambda.py      # Correlation Lambda
├── update-detection-opensearch.py    # Detection Lambda
├── update-postmortem-lambda.py       # Postmortem Lambda
├── update-rca-lambda-v2.py           # Root Cause Analysis Lambda
├── update-remediation-lambda2.py     # Remediation Recommendations Lambda
└── update-scoring-lambda.py          # Severity Scoring Lambda
```

## Key Notes

### Stack vs Script Code Management

The CloudFormation stacks contain **placeholder code** for most Lambdas. The actual runtime code is deployed via Python scripts in `scripts/lambdas/`. This is by design:

1. **Stacks define infrastructure**: IAM roles, permissions, environment variables, log groups
2. **Scripts deploy code**: The actual Lambda function code with business logic

### Deployment Workflow

1. Deploy CloudFormation stacks first (creates Lambda functions with placeholder code)
2. Run deployment scripts to update Lambda code with full implementation

```bash
# Deploy all Lambda code
python scripts/lambdas/update-detection-opensearch.py
python scripts/lambdas/update-correlation-lambda.py
python scripts/lambdas/update-rca-lambda-v2.py
python scripts/lambdas/update-scoring-lambda.py
python scripts/lambdas/update-remediation-lambda2.py
python scripts/lambdas/update-postmortem-lambda.py
python scripts/lambdas/create-summary-lambda.py
python scripts/lambdas/update-agent-invoker.py
python scripts/lambdas/update-agent-actions-all-tools.py
```

### Agent Investigation Tools (6 Tools)

The `outageshield-agent-actions-dev` Lambda provides 6 investigation tools:

| Tool | API Path | Data Source |
|------|----------|-------------|
| searchIncidentHistory | /search-incidents | DynamoDB (incidents table) |
| searchLogs | /search-logs | OpenSearch Serverless |
| getRunbook | /get-runbook | DynamoDB (runbooks table) |
| checkDeployments | /check-deployments | DynamoDB (deployments table) |
| searchTraces | /search-traces | AWS X-Ray |
| checkConfigDrift | /check-config-drift | AWS Config |

The `outageshield-agent-invoker-dev` Lambda directly calls all 6 tools to ensure complete investigation coverage.

## Environment Variables

All Lambdas use these common environment variables:
- `ENVIRONMENT`: dev/staging/prod
- `INCIDENTS_TABLE`: outageshield-incidents-dev
- `EVENTS_TABLE`: outageshield-events-dev
- `RUNBOOKS_TABLE`: outageshield-runbooks-dev
- `DEPLOYMENTS_TABLE`: outageshield-deployments-dev
- `OPENSEARCH_ENDPOINT`: OpenSearch Serverless endpoint
- `MODEL_ID`: Bedrock model ID (for AI-powered Lambdas)

## Step Functions Workflow

The `outageshield-workflow-dev` state machine (06-orchestration-stack.yaml) orchestrates:

1. **Step1_Correlate** → outageshield-correlation-dev
2. **Step2_Score** → outageshield-scoring-dev
3. **Step3_RootCause** → outageshield-rootcause-dev
4. **Step3b_AgentInvestigation** → outageshield-agent-invoker-dev (calls 6 tools)
5. **Step4_Remediation** → outageshield-remediation-recommend-dev
6. **Step4b_Summary** → outageshield-remediation-summary-dev
7. **Step5_CheckApproval** → Choice state
8. **Step6_Execute** → outageshield-remediation-executor-dev (if approved)
9. **Step7_CreateTicket** → outageshield-ticket-dev
10. **Step8_Notify** → outageshield-notification-dev
11. **Step9_Postmortem** → outageshield-postmortem-dev

## DynamoDB Tables

- `outageshield-incidents-dev` - Main incidents table
- `outageshield-events-dev` - Detection events
- `outageshield-runbooks-dev` - Remediation runbooks
- `outageshield-deployments-dev` - Deployment history (with GSI: service-timestamp-index)
- `outageshield-postmortems-dev` - Generated postmortems
- `outageshield-ai-reasoning-dev` - AI reasoning logs

## Recent Updates (May 2026)

1. **Agent Invoker Refactored**: Now directly calls all 6 tools via agent-actions Lambda instead of relying on Bedrock Agent autonomy. This guarantees all tools are called every time.

2. **Agent Actions Lambda**: Consolidated all 6 investigation tools into a single Lambda with proper API routing.

3. **Summary Lambda**: Generates AI-powered summaries with smart quick actions based on actual investigation and remediation data.

4. **Postmortem Lambda**: Uses actual remediation and investigation data to generate accurate postmortems.
