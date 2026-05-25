# OutageShield AI — CloudFormation Stacks

## Stack Overview

| # | Stack | File | Description |
|---|-------|------|-------------|
| 1 | Storage | `02-storage-stack.yaml` | DynamoDB tables + OpenSearch domain |
| 2 | Notifications | `07-notifications-stack.yaml` | SNS topics + Notification Lambda + Ticket Integrator (Jira + PagerDuty) |
| 3 | Ingestion | `01-ingestion-stack.yaml` | EventBridge rules + Ingestion Lambda |
| 4 | Detection | `03-detection-stack.yaml` | Detection Lambda + Outage Signal bus |
| 5 | Correlation | `04-correlation-stack.yaml` | Correlation Lambda (context builder) |
| 6 | Reasoning | `05-reasoning-stack.yaml` | Bedrock AI — Root Cause + Remediation (6 sources) + Scoring + Postmortem |
| 7 | Orchestration | `06-orchestration-stack.yaml` | Step Functions state machine (10-step workflow) |
| 8 | Remediation | `08-remediation-stack.yaml` | Remediation Executor Lambda + SSM Documents |
| 9 | Dashboard | `09-dashboard-stack.yaml` | API Gateway + Dashboard API Lambda |
| 10 | Auth | `10-auth-stack.yaml` | Amazon Cognito (user pool + app client) |
| 11 | WebSocket | `11-websocket-stack.yaml` | WebSocket API (real-time streaming) |
| 12 | CloudFront | `12-cloudfront-stack.yaml` | S3 + CloudFront (UI hosting) |
| 13 | Bedrock Agent | `13-bedrock-agent-stack.yaml` | Autonomous investigation agent (6 tools) + Anti-hallucination design |
| 14 | CloudTrail | `14-cloudtrail-deployments-stack.yaml` | CloudTrail for deployment tracking |
| 15 | X-Ray/Config | `15-xray-config-stack.yaml` | X-Ray tracing + AWS Config drift detection |

## Key Features

### Investigation Tools (6 total)
1. **searchIncidentHistory** - Query past incidents from DynamoDB
2. **searchLogs** - Query OpenSearch for log patterns
3. **getRunbook** - Look up remediation runbooks
4. **checkDeployments** - Check recent deployments and config changes
5. **searchTraces** - Query AWS X-Ray for latency/error traces
6. **checkConfigDrift** - Check AWS Config for compliance issues

### Remediation Sources (6 total)
1. **AGENT:deployment_correlation** - Deployment-related recommendations
2. **AGENT:log_patterns** - Log pattern analysis
3. **AGENT:runbook** - Runbook-based remediation steps
4. **AGENT:past_incidents** - Historical incident patterns
5. **AGENT:xray_traces** - X-Ray trace analysis
6. **AGENT:config_drift** - AWS Config compliance recommendations

### Ticketing Integration
- **Jira** - Full integration with Atlassian Jira
- **PagerDuty** - Full integration with PagerDuty Events API v2
- **Configurable** - Use Jira only, PagerDuty only, or both

### Anti-Hallucination Design
- Bedrock Agent calls tools with `enableTrace=True`
- Raw tool results extracted from trace (not LLM text)
- Pure rule-based output formatting
- No AI interpretation = No hallucination

## Dependency Graph

```
                    ┌──────────┐
                    │ Storage  │ (02)
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────────────────────┐
          │              │              │                │
          ▼              ▼              ▼                ▼
   ┌─────────────┐ ┌──────────┐ ┌───────────┐  ┌────────────┐
   │Notifications│ │Ingestion │ │ Detection │  │ Correlation│
   │    (07)     │ │   (01)   │ │   (03)    │  │    (04)    │
   └──────┬──────┘ └──────────┘ └───────────┘  └─────┬──────┘
          │                                           │
          │         ┌───────────┐                     │
          │         │ Reasoning │ (05)                │
          │         └─────┬─────┘                     │
          │               │                           │
          └───────────────┼───────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ Orchestration │ (06)
                  └───────┬───────┘
                          │
               ┌──────────┼──────────┐
               ▼          ▼          ▼
       ┌─────────────┐ ┌────────┐ ┌───────────────┐
       │ Remediation │ │Dashboard│ │ Bedrock Agent │
       │    (08)     │ │  (09)  │ │     (13)      │
       └─────────────┘ └────┬───┘ └───────────────┘
                            │
                    ┌───────┼───────┐
                    ▼       ▼       ▼
              ┌──────┐ ┌────────┐ ┌──────────┐
              │ Auth │ │WebSocket│ │CloudFront│
              │ (10) │ │  (11)  │ │   (12)   │
              └──────┘ └────────┘ └──────────┘
```

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- Sufficient IAM permissions for CloudFormation, Lambda, DynamoDB, OpenSearch, Step Functions, API Gateway, SNS, SSM, EventBridge

### Deploy All Stacks

```bash
cd stacks
chmod +x deploy.sh
./deploy.sh dev us-east-1
```

### Deploy Individual Stack

```bash
aws cloudformation deploy \
  --stack-name outageshield-storage-dev \
  --template-file 02-storage-stack.yaml \
  --parameter-overrides Environment=dev \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Tear Down

```bash
# Delete in reverse order
for stack in dashboard remediation orchestration reasoning correlation detection ingestion notifications storage; do
  aws cloudformation delete-stack --stack-name "outageshield-${stack}-dev" --region us-east-1
  aws cloudformation wait stack-delete-complete --stack-name "outageshield-${stack}-dev" --region us-east-1
done
```

## Parameters

All stacks accept:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Environment` | `dev` | Deployment environment (dev/staging/prod) |
| `RetentionDays` | `14` | CloudWatch log retention |

Stack-specific parameters:

| Stack | Parameter | Default | Description |
|-------|-----------|---------|-------------|
| Storage | `OpenSearchInstanceType` | `t3.small.search` | OpenSearch node type |
| Storage | `OpenSearchInstanceCount` | `1` | Number of data nodes |
| Reasoning | `BedrockModelId` | `anthropic.claude-3-sonnet-20240229-v1:0` | Foundation model |
| Notifications | `OpsEmailEndpoint` | `ops-team@example.com` | Alert email |

## Cross-Stack References

Stacks communicate via CloudFormation exports. Key exports:

- `outageshield-storage-{env}-EventsTableName`
- `outageshield-storage-{env}-EventsTableArn`
- `outageshield-storage-{env}-IncidentsTableName`
- `outageshield-storage-{env}-IncidentsTableArn`
- `outageshield-storage-{env}-OpenSearchEndpoint`
- `outageshield-notifications-{env}-TopicArn`
- `outageshield-notifications-{env}-LambdaArn`
- `outageshield-notifications-{env}-TicketLambdaArn`
- `outageshield-reasoning-{env}-RootCauseLambdaArn`
- `outageshield-reasoning-{env}-RemediationLambdaArn`
- `outageshield-reasoning-{env}-ScoringLambdaArn`
- `outageshield-reasoning-{env}-PostmortemLambdaArn`
- `outageshield-remediation-{env}-ExecutorLambdaArn`
- `outageshield-orchestration-{env}-StateMachineArn`
- `outageshield-dashboard-{env}-ApiUrl`
- `outageshield-bedrock-agent-{env}-AgentId`
- `outageshield-bedrock-agent-{env}-AgentArn`

## PagerDuty Integration Setup

### 1. Create PagerDuty Account

Sign up for PagerDuty (free tier available):
https://www.pagerduty.com/sign-up-free/

### 2. Create a Service with Events API v2

1. Go to **Services > Service Directory > + New Service**
2. Name: `OutageShield AI`
3. Integration: Select **Events API v2**
4. Copy the **Integration Key** (routing key)

### 3. Create PagerDuty Secret

```bash
aws secretsmanager update-secret \
  --secret-id outageshield/pagerduty-credentials \
  --secret-string '{
    "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY",
    "api_key": ""
  }'
```

### 4. Configure Ticket System

Update the `TICKET_SYSTEM` environment variable on the ticket-integrator Lambda:

| Value | Behavior |
|-------|----------|
| `jira` | Create tickets in Jira only |
| `pagerduty` | Create incidents in PagerDuty only |
| `both` | Create tickets in both systems (default) |

```bash
aws lambda update-function-configuration \
  --function-name outageshield-ticket-integrator-dev \
  --environment "Variables={TICKET_SYSTEM=both,...}"
```

### 5. PagerDuty Features

- **Events API v2** - Industry standard for incident creation
- **Severity Mapping** - SEV-5/4 → critical, SEV-3 → error, SEV-2 → warning, SEV-1 → info
- **Deduplication** - Uses incident_id as dedup_key to prevent duplicates
- **Dashboard Link** - Included in custom_details for quick access
- **Real-time Alerts** - Immediate notification via PagerDuty mobile app

## Lambda Code Deployment

Some Lambdas have placeholder code in CloudFormation. Deploy full code via scripts:

```bash
# Agent Actions (6 investigation tools)
python scripts/lambdas/add-xray-config-tools.py

# Agent Invoker (anti-hallucination design)
python scripts/lambdas/update-agent-invoker.py

# Remediation (6 sources, rule-based)
python scripts/lambdas/update-remediation-lambda2.py

# Ticket Integrator (Jira + PagerDuty)
python scripts/lambdas/add-pagerduty-integration.py
```

