# OutageShield AI — CloudFormation Stacks

## Stack Overview

| # | Stack | File | Description |
|---|-------|------|-------------|
| 1 | Storage | `02-storage-stack.yaml` | DynamoDB tables + OpenSearch domain |
| 2 | Notifications | `07-notifications-stack.yaml` | SNS topics + Notification Lambda + Ticket Integrator |
| 3 | Ingestion | `01-ingestion-stack.yaml` | EventBridge rules + Ingestion Lambda |
| 4 | Detection | `03-detection-stack.yaml` | Detection Lambda + Outage Signal bus |
| 5 | Correlation | `04-correlation-stack.yaml` | Correlation Lambda (context builder) |
| 6 | Reasoning | `05-reasoning-stack.yaml` | Bedrock AI — Root Cause + Remediation + Scoring + Postmortem Lambdas |
| 7 | Orchestration | `06-orchestration-stack.yaml` | Step Functions state machine (10-step workflow) |
| 8 | Remediation | `08-remediation-stack.yaml` | Remediation Executor Lambda + SSM Documents |
| 9 | Dashboard | `09-dashboard-stack.yaml` | API Gateway + Dashboard API Lambda |
| 10 | Auth | `10-auth-stack.yaml` | Amazon Cognito (user pool + app client) |
| 11 | WebSocket | `11-websocket-stack.yaml` | WebSocket API (real-time streaming) |
| 12 | CloudFront | `12-cloudfront-stack.yaml` | S3 + CloudFront (UI hosting) |
| 13 | Bedrock Agent | `13-bedrock-agent-stack.yaml` | Autonomous incident investigation agent + Action Groups |

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



C:\Users\mari8947\OneDrive - Rackspace Inc\Desktop\OutageShield AI\README.md update the End-to-End Flow for the current used