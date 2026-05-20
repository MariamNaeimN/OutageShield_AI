# OutageShield AI

**Agent 3** — AI-powered incident detection, correlation, and remediation platform for enterprise cloud operations.

---

## Problem

Enterprises lose revenue, customer trust, and engineering productivity when applications or cloud environments experience outages. Existing monitoring tools generate alerts, but teams still struggle to connect logs, telemetry, deployments, infrastructure changes, and past incidents quickly enough to prevent downtime or reduce recovery time.

## Solution

OutageShield AI analyzes operational data and automatically:

- Detects early outage signals
- Correlates alerts, logs, telemetry, and deployment history
- Identifies likely root cause using Amazon Bedrock
- Recommends rollback, scaling, configuration, or remediation actions
- Generates incident summaries and postmortem drafts
- Triggers tickets or workflows in ServiceNow/Jira
- Pauses for human approval before executing remediation (each incident independent)

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
├── README.md                          ← You are here
│
├── stacks/                            ← AWS CloudFormation infrastructure
│   ├── 01-ingestion-stack.yaml        ← EventBridge + Ingestion Lambda
│   ├── 02-storage-stack.yaml          ← DynamoDB (5 tables) + OpenSearch
│   ├── 03-detection-stack.yaml        ← Detection Lambda + Signal bus
│   ├── 04-correlation-stack.yaml      ← Correlation Lambda (context builder)
│   ├── 05-reasoning-stack.yaml        ← Bedrock Agent (RCA, remediation, scoring, postmortem)
│   ├── 06-orchestration-stack.yaml    ← Step Functions state machine
│   ├── 07-notifications-stack.yaml    ← SNS + Notification Lambda + Ticket Integrator
│   ├── 08-remediation-stack.yaml      ← Remediation Executor + SSM Documents
│   ├── 09-dashboard-stack.yaml        ← API Gateway + Dashboard API Lambda
│   ├── deploy.sh                      ← Deploy all stacks in dependency order
│   ├── README.md                      ← Stack documentation + dependency graph
│   └── stepfunctions/
│       ├── incident-workflow.asl.json  ← Full 27-state ASL definition
│       ├── approval-lambda.py         ← Human approval callback handler
│       └── README.md                  ← State machine visual flow + docs
│
├── UI/                                ← React Incident Command Dashboard
│   ├── src/
│   │   ├── components/                ← Layout, SeverityBadge, StatusBadge, RiskIndicator
│   │   ├── pages/                     ← Dashboard, IncidentDetail, Postmortems
│   │   ├── services/
│   │   │   ├── api.ts                 ← REST API client (fetches from backend)
│   │   │   └── websocket.ts           ← WebSocket real-time streaming
│   │   ├── hooks/
│   │   │   └── useRealtime.ts         ← React hooks for live updates
│   │   ├── App.tsx                    ← Router setup
│   │   ├── main.tsx                   ← Entry point
│   │   └── index.css                  ← Tailwind + custom styles
│   ├── .env.example                   ← API URL configuration
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── scripts/                           ← Demo & testing tools
│   ├── demo-test-events.json          ← 4 scenarios, 16 test events
│   ├── generate-test-data.py          ← Python script to push events to AWS
│   └── run-demo.sh                    ← Push test data + cleanup after demo
│
├── docs/
│   └── data-ingestion-guide.md        ← How data flows into the system
│
└── .kiro/specs/outageshield-ai/       ← Requirements specification
    ├── requirements.md                ← 12 detailed requirements (EARS format)
    └── .config.kiro                   ← Spec configuration
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
│  AWS Lambda — Ingestion (normalize + dedupe + store)                     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AWS Lambda — Detection (thresholds, patterns, anomalies)               │
│  Generates Outage Signals → publishes to Signal Bus                     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AWS Step Functions — Incident Investigation Workflow                    │
│                                                                         │
│  Correlate → Score → RCA → Recommend → [Human Approval] → Execute      │
│                                              ⏸ pauses                   │
│                                              indefinitely               │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌─────────────────┐
│ Amazon Bedrock   │ │ DynamoDB │ │ Systems Manager  │
│ (Root Cause,     │ │ + Open-  │ │ (Execute         │
│  Remediation,    │ │ Search   │ │  rollback/scale) │
│  Postmortem)     │ │          │ │                  │
└──────────────────┘ └──────────┘ └─────────────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Output Layer                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ SNS Alerts   │  │ Jira/SNOW    │  │ React Dashboard (WebSocket)  │  │
│  │ (PagerDuty,  │  │ Tickets      │  │ Real-time incident command   │  │
│  │  Slack, SMS) │  │              │  │                              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### AWS Services Used

| Service | Role |
|---------|------|
| Amazon CloudWatch | Metrics, logs, and alarms ingestion |
| AWS X-Ray | Application tracing and dependency insights |
| AWS CloudTrail | API activity and change tracking |
| AWS Config | Configuration state and drift detection |
| Amazon EventBridge | Event routing and incident triggers |
| AWS Lambda | Alert processing, detection, correlation, notification |
| AWS Step Functions | Incident workflow orchestration (27 states) |
| Amazon Bedrock | Root-cause analysis, remediation, scoring, postmortem generation |
| Amazon DynamoDB | Incident history, runbooks, workflow state (365-day retention) |
| Amazon OpenSearch | Full-text search, log correlation, pattern analysis |
| AWS Systems Manager | Execute approved remediation (rollback, scale, config) |
| Amazon SNS | Multi-channel notifications (email, SMS, Slack, PagerDuty) |
| API Gateway (REST) | Dashboard API backend |
| API Gateway (WebSocket) | Real-time streaming to UI |
| ServiceNow / Jira | Ticket creation and incident tracking |

---

## Demo Workflow

```
1. ALERT         → CloudWatch detects increased API latency
2. DETECT        → Detection Engine generates Outage Signal (severity: 4)
3. CORRELATE     → Agent reviews logs, metrics, traces, deploys, config changes
4. ROOT CAUSE    → Bedrock identifies: latency after deploy + DB connection spike (87% confidence)
5. RECOMMEND     → Rollback to v86 (effectiveness: 5/5, risk: low, TTR: 5 min)
6. APPROVAL      → Workflow PAUSES — shows "Awaiting Approval" in dashboard
7. HUMAN APPROVES → Engineer clicks "Approve" in UI
8. EXECUTE       → Systems Manager rolls back deployment
9. TICKET        → Jira ticket created with full context
10. NOTIFY       → Team alerted via PagerDuty
11. POSTMORTEM   → AI generates incident summary + prevention steps
```

Each incident runs as its own Step Functions execution — multiple incidents are handled in parallel independently.

---

## Quick Start

### 1. Deploy Infrastructure

```bash
cd stacks
chmod +x deploy.sh
./deploy.sh dev us-east-1
```

### 2. Run the Dashboard

```bash
cd UI
npm install
cp .env.example .env.local
# Edit .env.local with your API Gateway URL
npm run dev
```

Opens at `http://localhost:3000`

### 3. Push Test Data

```bash
# Push all 4 test scenarios
./scripts/run-demo.sh push

# Or just the full outage scenario
./scripts/run-demo.sh push 4

# Clean up after demo
./scripts/run-demo.sh cleanup
```

---

## Step Functions Workflow

The incident investigation workflow has **27 states** with full error handling:

```
InitializeIncident → CorrelateContext → ScoreIncident → CheckEscalation
  → (sev≥4) SendEscalationAlert
  → AnalyzeRootCause → RecommendRemediation → CheckAutoRemediation
    → (auto=true) WaitForHumanApproval ← PAUSES INDEFINITELY
    → (approved) ExecuteRemediation
  → CreateTicket → NotifyTeam → DetermineWorkflowStatus
    → WorkflowResolved | WorkflowDegraded
```

**Human-in-the-loop:** The workflow pauses at `WaitForHumanApproval` using `.waitForTaskToken`. No ticket or notification is sent until the human approves. Each incident is independent — one paused approval doesn't block others.

See `stacks/stepfunctions/README.md` for the full visual flow.

---

## Data Ingestion

| Source | Method | Latency |
|--------|--------|---------|
| CloudWatch Alarms | Push (EventBridge) | < 10s |
| CloudTrail | Push (EventBridge) | < 5 min |
| AWS Config | Push (EventBridge) | < 5 min |
| CloudWatch Logs | Push (Subscription Filter) | < 5s |
| X-Ray Traces | Pull (scheduled Lambda) | < 60s |
| CloudWatch Metrics | Pull (scheduled Lambda) | < 60s |

See `docs/data-ingestion-guide.md` for full details.

---

## React Dashboard

Professional dark-theme incident command interface:

- **Dashboard** — Active incidents (sorted by severity), service risk overview, stats
- **Incident Detail** — Root cause + confidence, ranked recommendations, timeline, workflow progress, approve/reject buttons
- **Postmortems** — AI-generated reports with prevention steps
- **Real-time** — WebSocket streaming for instant updates (falls back to 10s polling)

Tech stack: Vite + React 18 + TypeScript + Tailwind CSS + Recharts + Lucide Icons

---

## Test Data

4 demo scenarios available:

| # | Scenario | Signals |
|---|----------|---------|
| 1 | Latency spike | Metrics + alarm + X-Ray trace |
| 2 | Deployment failure | CloudTrail deploy + errors + alarm |
| 3 | Config drift | Config change + connection exhaustion + alarm |
| 4 | Full outage | Deploy + config + latency + errors + 3 alarms + X-Ray faults |

All test data is removable with `./scripts/run-demo.sh cleanup`. Nothing persists in CloudTrail beyond normal API activity logs (which age out automatically).

---

## Definition of Done

- ✅ Agent detects and correlates alerts, logs, telemetry, and changes
- ✅ Agent identifies likely root cause and recommends remediation steps
- ✅ User can view outage risk, business impact, and incident status in dashboard
- ✅ System can create tickets and generate incident/postmortem summaries
- ✅ System runs on AWS using CloudWatch, X-Ray, CloudTrail, Config, OpenSearch, Bedrock, Lambda, Step Functions, EventBridge, DynamoDB, Systems Manager, SNS, and ticketing integrations
- ✅ Human approval gate pauses workflow indefinitely per incident
- ✅ Multiple incidents run in parallel independently
- ✅ Real-time dashboard updates via WebSocket
- ✅ Demo test data with full cleanup
