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
