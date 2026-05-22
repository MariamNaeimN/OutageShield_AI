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
- Trigger tickets or workflows in ServiceNow/Jira

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
├── stacks/                            ← AWS CloudFormation (12 stacks)
│   ├── 01-ingestion-stack.yaml        ← EventBridge + Ingestion Lambda
│   ├── 02-storage-stack.yaml          ← DynamoDB (5 tables) + OpenSearch Serverless
│   ├── 03-detection-stack.yaml        ← Detection Lambda + X-Ray tracing
│   ├── 04-correlation-stack.yaml      ← Correlation Lambda (context builder)
│   ├── 05-reasoning-stack.yaml        ← Bedrock AI (RCA, remediation, scoring, postmortem)
│   ├── 06-orchestration-stack.yaml    ← Step Functions (10-step workflow + X-Ray)
│   ├── 07-notifications-stack.yaml    ← SNS + Notification Lambda + Ticket Lambda
│   ├── 08-remediation-stack.yaml      ← Remediation Executor + SSM Documents
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
│   │   ├── components/                ← Layout, SeverityBadge, StatusBadge
│   │   ├── pages/                     ← Dashboard, Incidents, IncidentDetail,
│   │   │                                 Postmortems, Notifications, TicketDetail, SnsDetail
│   │   ├── services/
│   │   │   ├── api.ts                 ← REST API client
│   │   │   ├── auth.ts               ← Cognito authentication
│   │   │   └── websocket.ts          ← WebSocket real-time
│   │   └── hooks/useRealtime.ts
│   ├── public/favicon.svg             ← Custom shield favicon
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── scripts/
│   ├── run-demo-60.py                 ← Trigger 60 incidents (full pipeline)
│   ├── delete-all.sh                  ← Delete all AWS resources
│   ├── run-demo.sh                    ← Quick demo runner
│   └── setup-opensearch-indexes.py    ← OpenSearch index setup
│
├── docs/
│   ├── data-ingestion-guide.md        ← Data flow documentation
│   └── continuous-learning.md         ← AI learning patterns
│
└── image/
    └── Project_Flow.png               ← Architecture diagram
```

---

## AWS Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                     │
│  CloudWatch │ X-Ray │ CloudTrail │ AWS Config                           │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Amazon EventBridge — routes events to processing pipeline              │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AWS Lambda — Detection (thresholds + anomaly detection)                │
│  Stores event → Starts Step Functions workflow                           │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AWS Step Functions — 10-Step Incident Investigation Workflow            │
│                                                                         │
│  1. Correlate → 2. Score → 3. RCA → 4. Remediation → 5. Approval       │
│  → 6. Execute → 7. Ticket → 8. Notify → 9. Postmortem → 10. Done       │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌─────────────────┐
│ Amazon Bedrock   │ │ DynamoDB │ │ Systems Manager  │
│ Claude 3 Haiku   │ │ (5 tables)│ │ (Remediation)   │
│ - Scoring        │ │ + Open-  │ │                  │
│ - Root Cause     │ │   Search │ │                  │
│ - Remediation    │ │          │ │                  │
│ - Postmortem     │ │          │ │                  │
└──────────────────┘ └──────────┘ └─────────────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Output Layer                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Amazon SNS   │  │ Jira/SNOW    │  │ React Dashboard              │  │
│  │ (Alerts)     │  │ Tickets      │  │ (CloudFront + WebSocket)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### AWS Services Used

| Service | Role |
|---------|------|
| Amazon CloudWatch | Metrics, logs, and alarms ingestion |
| AWS X-Ray | Application tracing (Active on all Lambdas + Step Functions) |
| AWS CloudTrail | API activity and change tracking |
| AWS Config | Configuration state and drift detection |
| Amazon EventBridge | Event routing and incident triggers |
| AWS Lambda | Detection, correlation, scoring, RCA, remediation, ticket, notify, postmortem, dashboard |
| AWS Step Functions | 10-step incident workflow orchestration (X-Ray enabled) |
| Amazon Bedrock | Claude 3 Haiku — root-cause analysis, scoring, remediation, postmortem |
| Amazon Bedrock Agents | Autonomous incident investigation agent with Action Groups (search incidents, logs, runbooks, deployments) |
| Amazon DynamoDB | 5 tables: events, incidents, runbooks, workflow-state, postmortems |
| Amazon OpenSearch Serverless | Log search and incident correlation |
| AWS Systems Manager | Execute approved remediation actions |
| Amazon SNS | Multi-channel notifications |
| Amazon Cognito | User authentication (user pool + app client) |
| API Gateway (REST) | Dashboard API backend (/incidents, /risk, /postmortems, /events) |
| API Gateway (WebSocket) | Real-time streaming to UI |
| Amazon S3 | Static UI hosting |
| Amazon CloudFront | CDN for UI (HTTPS, SPA routing) |
| ServiceNow / Jira | Ticket creation and incident tracking |

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
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 1: CORRELATE                                              │  │
│  │ Lambda: outageshield-correlation-dev                           │  │
│  │ Action: Gathers logs, metrics, traces, deployments, configs    │  │
│  │ Writes: Creates incident record in outageshield-incidents-dev  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 2: SCORE                                                  │  │
│  │ Lambda: outageshield-scoring-dev + Amazon Bedrock              │  │
│  │ Action: Evaluates severity, business impact, revenue at risk,  │  │
│  │         affected users, SLA status, service risk score         │  │
│  │ Writes: severity_score, business_impact_score, revenue_at_risk,│  │
│  │         affected_users, sla_status, scoring_reasoning          │  │
│  │         → outageshield-incidents-dev                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 3: ROOT CAUSE ANALYSIS                                    │  │
│  │ Lambda: outageshield-root-cause-dev + Amazon Bedrock           │  │
│  │ Action: Analyzes all context to identify probable root cause   │  │
│  │ Writes: root_cause, confidence                                 │  │
│  │         → outageshield-incidents-dev                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 4: REMEDIATION RECOMMENDATIONS                            │  │
│  │ Lambda: outageshield-remediation-dev + Amazon Bedrock          │  │
│  │ Action: Generates ranked fix options (rollback, scale, config) │  │
│  │ Writes: recommendations_raw (JSON array with confidence,       │  │
│  │         risk, estimated TTR)                                   │  │
│  │         → outageshield-incidents-dev                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 5: APPROVAL GATE ⚠️ FUTURE FEATURE                       │  │
│  │ Action: Checks $.signal.auto_remediation_enabled               │  │
│  │         If true → pause workflow (waitForTaskToken) until       │  │
│  │                    human approves/rejects via dashboard or API  │  │
│  │         If false/missing (current default) → skip to Step 7    │  │
│  │                                                                │  │
│  │ NOTE: Currently all incidents skip this step (auto_remediation │  │
│  │ is not set in alarm events). In production, this will enable   │  │
│  │ human-in-the-loop approval before executing remediation.       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 6: EXECUTE REMEDIATION                                    │  │
│  │ Lambda: outageshield-remediation-executor-dev                  │  │
│  │ Action: Calls AWS Systems Manager to execute approved action   │  │
│  │         - Rollback: SSM SendCommand to target instances        │  │
│  │         - Scaling: Updates Auto Scaling Group capacity          │  │
│  │         - Config: SSM SendCommand with config update scripts   │  │
│  │ Writes: remediation result → outageshield-incidents-dev        │  │
│  │                                                                │  │
│  │ NOTE: Only executes when Step 5 approval gate is passed.       │  │
│  │ Currently requires auto_remediation_enabled=true in signal.    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 7: CREATE TICKET                                          │  │
│  │ Lambda: outageshield-ticket-integrator-dev                     │  │
│  │ Action: Creates Jira ticket via REST API v3 with full context  │  │
│  │         Includes: incident details, root cause, dashboard link │  │
│  │ Writes: ticket_id, ticket_system, ticket_status, ticket_url,   │  │
│  │         ticket_content → outageshield-incidents-dev            │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 8: NOTIFY                                                 │  │
│  │ Lambda: outageshield-notification-dev                          │  │
│  │ Action: Sends SNS alert (email, Slack, PagerDuty)              │  │
│  │         Includes ticket link + incident details                │  │
│  │ Writes: notifications (JSON) → outageshield-incidents-dev      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 9: POSTMORTEM                                             │  │
│  │ Lambda: outageshield-postmortem-dev + Amazon Bedrock           │  │
│  │ Action: Generates full postmortem report with:                 │  │
│  │         - Summary, duration, root cause                        │  │
│  │         - Impact assessment                                    │  │
│  │         - Prevention recommendations (long-term)               │  │
│  │ Writes: → outageshield-postmortems-dev                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Step 10: DONE                                                  │  │
│  │ Workflow complete. All data stored in DynamoDB.                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Dashboard API         │  Reads from all DynamoDB tables
│   (09-dashboard-stack)  │  REST: /incidents, /risk, /postmortems, /events
│                         │  WebSocket: real-time updates
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   React UI              │  CloudFront + S3
│   (UI/src)              │  Dashboard, Incidents, Postmortems,
│                         │  Notifications, Ticket Details
└─────────────────────────┘
```

### DynamoDB Tables

| Table | Purpose | Written By |
|-------|---------|-----------|
| `outageshield-events-dev` | Raw alarm events | Detection Lambda (Step 0) |
| `outageshield-incidents-dev` | Enriched incidents (scores, root cause, recommendations, tickets, notifications) | Steps 1-8 |
| `outageshield-workflow-state-dev` | Workflow execution tracking | Step Functions |
| `outageshield-postmortems-dev` | AI postmortem reports with prevention steps | Postmortem Lambda (Step 9) |
| `outageshield-runbooks-dev` | Remediation runbook templates | Manual / Config |

---

## Demo Workflow

```
1. ALERT         → CloudWatch alarm triggers (e.g. HighLatency-payments-api)
2. DETECT        → Detection Lambda stores event + starts Step Functions
3. CORRELATE     → Correlation Lambda gathers logs, metrics, config changes
4. SCORE         → Bedrock evaluates: severity, business impact, revenue at risk, service risk
5. ROOT CAUSE    → Bedrock identifies probable root cause with confidence %
6. REMEDIATION   → Bedrock recommends ranked actions (rollback, scale, config)
7. TICKET        → Jira ticket created with full context + URL
8. NOTIFY        → SNS alert sent to SRE team
9. POSTMORTEM    → Bedrock generates incident summary + prevention steps
10. DONE         → All data stored in DynamoDB, visible in dashboard
```

All data is produced by the AI agent pipeline — no mock data.

---

## Quick Start

### 1. Deploy Infrastructure

```bash
cd stacks
chmod +x deploy.sh
./deploy.sh dev us-east-1
```

### 2. Run Demo (60 Incidents)

```bash
python scripts/run-demo-60.py
```

Triggers 60 incidents through the full pipeline. Wait 10-15 minutes for Bedrock to process all.

### 3. View Dashboard

**CloudFront:** `https://d2k1km1tzlio49.cloudfront.net`

**Local dev:**
```bash
cd UI
npm install
npm run dev
```

**Login:** `sre-team@shopsphere.com` / `OutageShield2024!`

### 4. Delete All Resources

```bash
./scripts/delete-all.sh
```

---

## React Dashboard

Professional dark-theme incident command interface:

- **Dashboard** — Active incidents with source, service risk (revenue at risk), stats cards, correlation events
- **Incidents** — Full incident list with search, severity, status, business impact, root cause
- **Incident Detail** — Root cause + confidence, recommendations, linked ticket, SNS notification, business details
- **Postmortems** — Master-detail layout with AI-generated reports, prevention steps
- **Notifications** — Tickets and SNS alerts (clickable → dedicated detail pages)
- **Login** — 2-section layout with Rackspace × AI Agent branding, Cognito auth

Tech stack: Vite + React 18 + TypeScript + Tailwind CSS + Recharts + Lucide Icons

---

## Engineering Tasks (Completed)

- ✅ Ingest CloudWatch metrics, logs, alarms, and operational events
- ✅ Correlate alerts with deployment events, configuration changes, and incident history
- ✅ Build root-cause reasoning workflow using Bedrock
- ✅ Map incidents to runbooks and recommended remediation actions
- ✅ Create incident severity scoring and business impact estimation
- ✅ Build dashboard for active incidents, outage risk, and recommended actions
- ✅ Integrate with ServiceNow/Jira for ticket creation and workflow handoff
- ✅ Generate post-incident summaries and prevention recommendations

---

## Definition of Done

- ✅ Agent detects and correlates alerts, logs, telemetry, and changes
- ✅ Agent identifies likely root cause and recommends remediation steps
- ✅ User can view outage risk, business impact, and incident status in dashboard
- ✅ System can create tickets and generate incident/postmortem summaries
- ✅ System runs on AWS using CloudWatch, X-Ray, CloudTrail, Config, OpenSearch, Bedrock, Lambda, Step Functions, EventBridge, DynamoDB, Systems Manager, SNS, and ticketing integrations

---

## Future Roadmap

| Feature | Status | Description |
|---------|--------|-------------|
| Human-in-the-Loop Approval (Step 5) | 🔮 Planned | Enable `auto_remediation_enabled` flag to pause workflow and wait for human approval via dashboard |
| Continuous Learning | 🔮 Planned | Feed resolved incident outcomes back to improve scoring and root cause accuracy |
| Multi-account Support | 🔮 Planned | Monitor incidents across multiple AWS accounts via Organizations |
| Slack/PagerDuty Integration | 🔮 Planned | Direct notification channels beyond SNS email |
| Runbook Automation | 🔮 Planned | Map incidents to SSM Automation documents for guided remediation |
