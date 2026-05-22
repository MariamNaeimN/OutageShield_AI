# OutageShield AI

**Agent 3** — AI-powered incident detection, correlation, and remediation platform for enterprise cloud operations.

---

## Problem

Enterprises lose revenue, customer trust, and engineering productivity when applications or cloud environments experience outages. Existing monitoring tools generate alerts, but teams still struggle to connect logs, telemetry, deployments, infrastructure changes, and past incidents quickly enough to prevent downtime or reduce recovery time.

## Primary Use Case

Analyze operational data and automatically:

- Detect early outage signals
- Correlate alerts, logs, telemetry, and deployment history
- Identify likely root cause using Amazon Bedrock
- Recommend rollback, scaling, configuration, or remediation actions
- Generate incident summaries and postmortem drafts
- Trigger tickets or workflows in Jira

## Target Customers

- Cloud operations teams
- Managed services providers
- SRE teams
- Platform engineering teams
- Enterprise IT operations
- CIO and infrastructure organizations

---

## Project Structure

```
OutageShield AI/
│
├── README.md
│
├── stacks/                            ← AWS CloudFormation (13 stacks)
│   ├── 01-ingestion-stack.yaml        ← EventBridge + Ingestion Lambda
│   ├── 02-storage-stack.yaml          ← DynamoDB (5 tables) + OpenSearch Serverless
│   ├── 03-detection-stack.yaml        ← Detection Lambda + X-Ray tracing
│   ├── 04-correlation-stack.yaml      ← Correlation Lambda (context builder)
│   ├── 05-reasoning-stack.yaml        ← Bedrock AI (RCA, remediation, scoring, postmortem)
│   ├── 06-orchestration-stack.yaml    ← Step Functions (10-step workflow + X-Ray)
│   ├── 07-notifications-stack.yaml    ← SNS + Notification Lambda + Jira Ticket Lambda
│   ├── 08-remediation-stack.yaml      ← Remediation Executor Lambda + SSM Documents
│   ├── 09-dashboard-stack.yaml        ← API Gateway + Dashboard API Lambda
│   ├── 10-auth-stack.yaml             ← Amazon Cognito (user pool + app client)
│   ├── 11-websocket-stack.yaml        ← WebSocket API (real-time streaming)
│   ├── 12-cloudfront-stack.yaml       ← S3 + CloudFront (UI hosting)
│   ├── 13-bedrock-agent-stack.yaml    ← Bedrock Agent (autonomous investigation)
│   ├── deploy.sh                      ← Deploy all stacks in order
│   └── stepfunctions/
│       ├── incident-workflow.asl.json  ← Full ASL definition
│       ├── approval-lambda.py         ← Human approval callback
│       └── README.md                  ← Workflow documentation
│
├── UI/                                ← React Incident Command Dashboard
│   ├── src/
│   │   ├── components/                ← Layout, SeverityBadge, StatusBadge, RiskIndicator
│   │   ├── pages/                     ← Dashboard, Incidents, IncidentDetail,
│   │   │                                 Postmortems, Notifications, TicketDetail, SnsDetail, Login
│   │   ├── services/
│   │   │   ├── api.ts                 ← REST API client (incidents, risk, postmortems, events)
│   │   │   ├── auth.ts               ← Cognito authentication
│   │   │   └── websocket.ts          ← WebSocket real-time updates
│   │   └── hooks/useRealtime.ts
│   ├── public/favicon.svg
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── scripts/
│   ├── run-demo-60.py                 ← Clear tables + trigger 100 incidents
│   ├── push-100.py                    ← Push 100 incidents (no clear)
│   ├── delete-jira-tickets.py         ← Delete all Jira tickets in TGSHLD project
│   ├── clean-and-push-100.py          ← Full reset: stop workflows, clear DB, delete Jira, push 100
│   ├── delete-all.sh                  ← Delete all AWS resources
│   └── setup-opensearch-indexes.py    ← OpenSearch index setup
│
└── docs/
    ├── data-ingestion-guide.md        ← Data flow documentation
    └── continuous-learning.md         ← AI learning patterns
```

---

## AWS Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                     │
│  CloudWatch Alarms │ X-Ray Traces │ CloudTrail │ AWS Config             │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Amazon EventBridge — routes alarm events to Detection Lambda            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Detection Lambda — stores event in DynamoDB, starts Step Functions      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AWS Step Functions — 10-Step Incident Investigation Workflow            │
│                                                                         │
│  1. Correlate → 2. Score → 3. RCA → 4. Remediation → 5. Approval       │
│  → 6. Execute (SSM) → 7. Jira Ticket → 8. SNS Notify → 9. Postmortem  │
│  → 10. Done                                                             │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┬────────────┐
              ▼            ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐
│ Amazon Bedrock   │ │ DynamoDB │ │ Bedrock  │ │ Systems Manager  │
│ Claude 3 Haiku   │ │ (5 tables)│ │ Agent    │ │ (Remediation)   │
│ - Scoring        │ │ + Open-  │ │ - Search │ │ - Rollback       │
│ - Root Cause     │ │   Search │ │ - Logs   │ │ - Scale          │
│ - Remediation    │ │          │ │ - Runbook│ │ - Config         │
│ - Postmortem     │ │          │ │ - Deploy │ │                  │
└──────────────────┘ └──────────┘ └──────────┘ └─────────────────┘
              │            │            │            │
              └────────────┴────────────┴────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Output Layer                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Amazon SNS   │  │ Jira Cloud   │  │ React Dashboard              │  │
│  │ (Alerts)     │  │ (Tickets)    │  │ (CloudFront + WebSocket)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### AWS Services Used

| Service | Role |
|---------|------|
| Amazon CloudWatch | Metrics, logs, and alarms ingestion |
| AWS X-Ray | Application tracing (active on all Lambdas + Step Functions) |
| AWS CloudTrail | API activity and change tracking |
| AWS Config | Configuration state and drift detection |
| Amazon EventBridge | Event routing and incident triggers |
| AWS Lambda | 10+ functions: detection, correlation, scoring, RCA, remediation, ticket, notify, postmortem, dashboard, agent actions |
| AWS Step Functions | 10-step incident workflow orchestration (X-Ray enabled) |
| Amazon Bedrock | Claude 3 Haiku — root-cause analysis, scoring, remediation, postmortem |
| Amazon Bedrock Agents | Autonomous incident investigation with Action Groups (search incidents, logs, runbooks, deployments) |
| Amazon DynamoDB | 5 tables: events, incidents, runbooks, workflow-state, postmortems |
| Amazon OpenSearch Serverless | Log search and incident correlation |
| AWS Systems Manager | Execute approved remediation (rollback, scale, config change) via SSM Documents |
| Amazon SNS | Multi-channel notifications (email, escalation) |
| Amazon Cognito | User authentication (user pool + app client) |
| API Gateway (REST) | Dashboard API (/incidents, /risk, /postmortems, /events, /approve) |
| API Gateway (WebSocket) | Real-time incident streaming to UI |
| Amazon S3 | Static UI hosting |
| Amazon CloudFront | CDN for UI (HTTPS, SPA routing) |
| Jira Cloud | Ticket creation via REST API v3 with dashboard links |

---

## Full Pipeline Flow

```
CloudWatch Alarm fires
        │
        ▼
┌─────────────────────────┐
│   Detection Lambda      │  Receives alarm event
│   (03-detection-stack)  │  Writes to: outageshield-events-dev
│                         │  Starts Step Functions workflow
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 STEP FUNCTIONS WORKFLOW                               │
│                 (06-orchestration-stack)                              │
│                                                                      │
│  Step 1: CORRELATE                                                   │
│  Lambda: outageshield-correlation-dev                                │
│  → Gathers logs, metrics, traces, deployments, configs               │
│  → Creates incident record in outageshield-incidents-dev             │
│                                                                      │
│  Step 2: SCORE                                                       │
│  Lambda: outageshield-scoring-dev + Amazon Bedrock                   │
│  → Evaluates severity, business impact, revenue at risk,             │
│    affected users, SLA status, service risk score                    │
│  → Writes: severity_score, business_impact_score, scoring_reasoning  │
│                                                                      │
│  Step 3: ROOT CAUSE ANALYSIS                                         │
│  Lambda: outageshield-root-cause-dev + Amazon Bedrock                │
│  → Analyzes all context to identify probable root cause              │
│  → Writes: root_cause, confidence                                    │
│                                                                      │
│  Step 4: REMEDIATION RECOMMENDATIONS                                 │
│  Lambda: outageshield-remediation-dev + Amazon Bedrock               │
│  → Generates ranked fix options (rollback, scale, config)            │
│  → Writes: recommendations_raw (JSON with confidence, risk, TTR)     │
│                                                                      │
│  Step 5: APPROVAL GATE                                               │
│  → Checks $.signal.auto_remediation_enabled                          │
│  → If true: pause for human approval (waitForTaskToken)              │
│  → If false (default): skip to Step 7                                │
│                                                                      │
│  Step 6: EXECUTE REMEDIATION                                         │
│  Lambda: outageshield-remediation-executor-dev                       │
│  → Calls AWS Systems Manager (SSM SendCommand)                       │
│  → Supports: rollback, scaling, configuration changes                │
│  → SSM Documents: OutageShield-Rollback, OutageShield-ScaleUp        │
│                                                                      │
│  Step 7: CREATE TICKET                                               │
│  Lambda: outageshield-ticket-integrator-dev                          │
│  → Creates Jira ticket via REST API v3 (ADF format)                  │
│  → Includes: incident details, root cause, dashboard link            │
│  → Writes: ticket_id, ticket_url, ticket_content                     │
│                                                                      │
│  Step 8: NOTIFY                                                      │
│  Lambda: outageshield-notification-dev                               │
│  → Sends SNS alert (escalation for SEV-4+, alert for lower)         │
│  → Includes: ticket link, root cause, revenue at risk                │
│  → Writes: notifications JSON                                        │
│                                                                      │
│  Step 9: POSTMORTEM                                                  │
│  Lambda: outageshield-postmortem-dev + Amazon Bedrock                │
│  → Generates full postmortem: summary, duration, root cause,         │
│    impact assessment, prevention recommendations                     │
│  → Writes to: outageshield-postmortems-dev                           │
│                                                                      │
│  Step 10: DONE                                                       │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Dashboard API         │  REST: /incidents, /risk, /postmortems, /events
│   (09-dashboard-stack)  │  WebSocket: real-time updates
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   React UI              │  CloudFront: https://d2k1km1tzlio49.cloudfront.net
│   (UI/src)              │  Jira: https://corpinfollc.atlassian.net/jira/software/projects/TGSHLD
└─────────────────────────┘
```

### Bedrock Agent (Autonomous Investigation)

In addition to the deterministic Step Functions workflow, a **Bedrock Agent** provides autonomous investigation capabilities:

```
Agent: outageshield-investigator-dev
Model: Claude 3 Haiku
Action Groups:
  /search-incidents  → Query DynamoDB for past incidents on the same service
  /search-logs       → Query OpenSearch/Events for error patterns
  /get-runbook       → Look up remediation runbook for the alarm type
  /check-deployments → Check recent deployments and config changes
```

The agent decides on its own which tools to call and how many iterations to perform, providing deeper investigation beyond the fixed workflow steps.

### DynamoDB Tables

| Table | Purpose | Written By |
|-------|---------|-----------|
| `outageshield-events-dev` | Raw alarm events | Detection Lambda |
| `outageshield-incidents-dev` | Enriched incidents (scores, root cause, recommendations, tickets, notifications) | Steps 1-8 |
| `outageshield-workflow-state-dev` | Workflow execution tracking | Step Functions |
| `outageshield-postmortems-dev` | AI postmortem reports with prevention steps | Postmortem Lambda (Step 9) |
| `outageshield-runbooks-dev` | Remediation runbook templates | Manual / Config |

---

## React Dashboard

Professional dark-theme incident command interface deployed on CloudFront.

| Page | Features |
|------|----------|
| **Dashboard** | Stats cards (active incidents, high-risk services, raw events), active incidents table with pagination, business impact overview (Critical/High/Medium/Low bars + donut chart), correlation events |
| **Incidents** | Full incident list with search, severity pills, status badges, business impact, root cause preview |
| **Incident Detail** | Root cause + confidence bar, AI recommendations, postmortem link, linked Jira ticket (opens in Jira), SNS notification, business details (revenue, users, SLA), workflow step |
| **Postmortems** | Master-detail layout, AI-generated reports with root cause, impact, scoring reasoning, prevention recommendations |
| **Notifications** | Tabs: Jira tickets (with external link to Jira) + SNS alerts, clickable to detail pages |
| **Ticket Detail** | Full ticket info, Jira link, dashboard link, description, priority, revenue/users/SLA |
| **Login** | Rackspace × AI Agent branding, Cognito authentication |

Tech stack: Vite + React 18 + TypeScript + Tailwind CSS + Recharts + Lucide Icons

---

## Demo

### Quick Start

```bash
# 1. Deploy all stacks
cd stacks && chmod +x deploy.sh && ./deploy.sh dev us-east-1

# 2. Push 100 incidents through the full AI pipeline
python scripts/push-100.py

# 3. Wait 15-20 minutes for Bedrock AI to process all workflows

# 4. View dashboard
# https://d2k1km1tzlio49.cloudfront.net
# Login: sre-team@shopsphere.com / OutageShield2024!
```

### Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/push-100.py` | Trigger 100 incidents through the pipeline |
| `scripts/run-demo-60.py` | Clear all tables + trigger 100 incidents |
| `scripts/delete-jira-tickets.py` | Delete all Jira tickets in TGSHLD project |
| `scripts/clean-and-push-100.py` | Full reset: stop workflows, clear DB, delete Jira, push 100 |
| `scripts/delete-all.sh` | Delete all AWS CloudFormation stacks |

### What Happens When You Push

```
1. ALARM       → CloudWatch alarm event sent to Detection Lambda
2. DETECT      → Event stored in DynamoDB, Step Functions workflow starts
3. CORRELATE   → Gathers context (logs, metrics, deployments, config)
4. SCORE       → Bedrock AI evaluates severity, business impact, revenue at risk
5. ROOT CAUSE  → Bedrock AI identifies probable root cause with confidence %
6. REMEDIATION → Bedrock AI recommends ranked actions (rollback, scale, config)
7. TICKET      → Jira ticket created with full context + dashboard link
8. NOTIFY      → SNS alert sent to SRE team with ticket link
9. POSTMORTEM  → Bedrock AI generates summary + prevention recommendations
10. DONE       → All data in DynamoDB, visible in dashboard in real-time
```

All data is produced by the AI agent pipeline — **no mock data**.

---

## Engineering Tasks (Completed)

- ✅ Ingest CloudWatch metrics, logs, alarms, and operational events
- ✅ Correlate alerts with deployment events, configuration changes, and incident history
- ✅ Build root-cause reasoning workflow using Amazon Bedrock
- ✅ Map incidents to runbooks and recommended remediation actions
- ✅ Create incident severity scoring and business impact estimation
- ✅ Build dashboard for active incidents, outage risk, and recommended actions
- ✅ Integrate with Jira for ticket creation and workflow handoff
- ✅ Generate post-incident summaries and prevention recommendations
- ✅ Wire remediation execution through AWS Systems Manager
- ✅ Add Bedrock Agent for autonomous incident investigation

---

## Definition of Done

- ✅ Agent detects and correlates alerts, logs, telemetry, and changes
- ✅ Agent identifies likely root cause and recommends remediation steps
- ✅ User can view outage risk, business impact, and incident status in dashboard
- ✅ System can create tickets and generate incident/postmortem summaries
- ✅ System runs on AWS using CloudWatch, X-Ray, CloudTrail, Config, OpenSearch, Bedrock, Bedrock Agents, Lambda, Step Functions, EventBridge, DynamoDB, Systems Manager, SNS, and Jira integration

---

## Future Roadmap

| Feature | Description |
|---------|-------------|
| Human-in-the-Loop Approval | Enable `auto_remediation_enabled` to pause workflow for human approval via dashboard |
| Continuous Learning | Feed resolved incident outcomes back to improve scoring and root cause accuracy |
| Multi-account Support | Monitor incidents across multiple AWS accounts via Organizations |
| Slack/PagerDuty Integration | Direct notification channels beyond SNS email |
| Runbook Automation | Map incidents to SSM Automation documents for guided remediation |
