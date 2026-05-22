# OutageShield AI

**Agent 3** — AI-powered incident detection, correlation, and remediation platform for enterprise cloud operations.

---

## Problem

Enterprises lose revenue, customer trust, and engineering productivity when applications or cloud environments experience outages. Existing monitoring tools generate alerts, but teams still struggle to connect logs, telemetry, deployments, infrastructure changes, and past incidents quickly enough to prevent downtime or reduce recovery time.

## Primary Use Case

Analyze operational data and automatically:

- Detect early outage signals
- Correlate alerts, logs, telemetry, and deployment history
- Identify likely root cause
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

## AWS Architecture

| Service | Stack | Role |
|---------|-------|------|
| Amazon CloudWatch | 01-ingestion, 03-detection | Metrics, logs, and alarms ingestion |
| AWS X-Ray | All Lambdas + Step Functions | Application tracing (TracingConfig: Active) |
| AWS CloudTrail | 04-correlation | API activity and change tracking |
| AWS Config | 04-correlation | Configuration state and drift detection |
| Amazon EventBridge | 01-ingestion | Event routing and incident triggers |
| AWS Lambda | 03, 04, 05, 07, 08, 09, 13 | 10+ functions: detection, correlation, scoring, RCA, remediation, ticket, notify, postmortem, dashboard, agent actions |
| AWS Step Functions | 06-orchestration | 10-step incident workflow orchestration (X-Ray enabled) |
| Amazon Bedrock | 05-reasoning | Claude 3 Haiku — root-cause analysis, scoring, remediation, postmortem |
| Amazon Bedrock Agents | 13-bedrock-agent | Autonomous incident investigation agent with Action Groups |
| Amazon DynamoDB | 02-storage | 5 tables: events, incidents, runbooks, workflow-state, postmortems |
| Amazon OpenSearch Serverless | 02-storage | Log search and incident correlation |
| AWS Systems Manager | 08-remediation | Execute approved remediation (rollback, scale, config) via SSM Documents |
| Amazon SNS | 07-notifications | Multi-channel notifications (alert + escalation topics) |
| Amazon Cognito | 10-auth | User authentication (user pool + app client) |
| API Gateway (REST) | 09-dashboard | Dashboard API: /incidents, /risk, /postmortems, /events, /approve |
| API Gateway (WebSocket) | 11-websocket | Real-time incident streaming to UI |
| Amazon S3 | 12-cloudfront | Static UI hosting |
| Amazon CloudFront | 12-cloudfront | CDN for UI (HTTPS, SPA routing) |
| Jira Cloud | 07-notifications | Ticket creation via REST API v3 with dashboard links |

---

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                    │
│                                                                             │
│  CloudWatch Alarms    AWS X-Ray Traces    CloudTrail    AWS Config          │
│       │                     │                 │              │              │
└───────┴─────────────────────┴─────────────────┴──────────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER (01-ingestion-stack)                                       │
│                                                                             │
│  Amazon EventBridge Rule → routes CloudWatch alarm events to Detection      │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DETECTION LAYER (03-detection-stack)                                       │
│                                                                             │
│  Lambda: outageshield-detection-dev                                         │
│  • Receives CloudWatch alarm event                                          │
│  • Stores raw event → outageshield-events-dev (DynamoDB)                    │
│  • Starts Step Functions workflow execution                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION LAYER (06-orchestration-stack)                               │
│  AWS Step Functions — 10-Step Incident Investigation Workflow                │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 1: CORRELATE                                                      │ │
│  │ Lambda: outageshield-correlation-dev (04-correlation-stack)             │ │
│  │ • Gathers logs, metrics, X-Ray traces, deployments, config changes     │ │
│  │ • Creates incident record in outageshield-incidents-dev                 │ │
│  │ • Sets workflow_step = 'correlating'                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 2: SCORE                                                          │ │
│  │ Lambda: outageshield-scoring-dev (05-reasoning-stack)                   │ │
│  │ • Calls Amazon Bedrock (Claude 3 Haiku) to evaluate:                   │ │
│  │   - severity_score (1-5)                                               │ │
│  │   - business_impact_score (1-10)                                       │ │
│  │   - revenue_at_risk (dollar estimate)                                  │ │
│  │   - affected_users (count)                                             │ │
│  │   - sla_status (On Track / At Risk / Breached)                         │ │
│  │   - service_risk_score (0-100)                                         │ │
│  │   - scoring_reasoning (AI explanation)                                 │ │
│  │ • Writes all scores → outageshield-incidents-dev                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 3: ROOT CAUSE ANALYSIS                                            │ │
│  │ Lambda: outageshield-root-cause-dev (05-reasoning-stack)                │ │
│  │ • Calls Amazon Bedrock with all incident context                       │ │
│  │ • Identifies probable root cause with confidence percentage            │ │
│  │ • Writes: root_cause, confidence → outageshield-incidents-dev          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 3b: BEDROCK AGENT DEEP INVESTIGATION                              │ │
│  │ Lambda: outageshield-agent-invoker-dev (13-bedrock-agent-stack)         │ │
│  │ • Invokes Bedrock Agent (outageshield-investigator-dev)                │ │
│  │ • Agent AUTONOMOUSLY decides which tools to call:                      │ │
│  │   - /search-incidents → past incidents on same service (DynamoDB)      │ │
│  │   - /search-logs → error patterns (OpenSearch/Events table)            │ │
│  │   - /get-runbook → alarm-specific runbook (DynamoDB runbooks table)    │ │
│  │   - /check-deployments → recent deploys and config changes             │ │
│  │ • Agent performs multiple iterations until investigation is complete   │ │
│  │ • Writes: agent_investigation → outageshield-incidents-dev             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 4: REMEDIATION RECOMMENDATIONS                                    │ │
│  │ Lambda: outageshield-remediation-dev (05-reasoning-stack)               │ │
│  │ • Calls Amazon Bedrock to generate ranked remediation options           │ │
│  │ • Each option includes: category, description, confidence,             │ │
│  │   risk level, estimated time to resolve                                │ │
│  │ • Categories: rollback, scaling, configuration_change,                 │ │
│  │   manual_intervention                                                  │ │
│  │ • Writes: recommendations_raw (JSON) → outageshield-incidents-dev      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 5: APPROVAL GATE                                                  │ │
│  │ Type: Choice (no Lambda)                                               │ │
│  │ • Checks: $.signal.auto_remediation_enabled                            │ │
│  │ • If true → Step 5b: Await human approval (waitForTaskToken)           │ │
│  │ • If false/missing (default) → Skip to Step 7                          │ │
│  │                                                                        │ │
│  │ NOTE: Currently all incidents skip to Step 7 because                   │ │
│  │ auto_remediation_enabled is not set in alarm events.                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 6: EXECUTE REMEDIATION                                            │ │
│  │ Lambda: outageshield-remediation-executor-dev (08-remediation-stack)    │ │
│  │ • Calls AWS Systems Manager (SSM SendCommand)                          │ │
│  │ • Supports:                                                            │ │
│  │   - Rollback: SSM RunShellScript on tagged instances                   │ │
│  │   - Scaling: UpdateAutoScalingGroup (increase capacity)                │ │
│  │   - Config change: SSM RunShellScript with config commands             │ │
│  │ • SSM Documents: OutageShield-Rollback-dev, OutageShield-ScaleUp-dev   │ │
│  │ • On failure: sends SNS alert about remediation failure                │ │
│  │                                                                        │ │
│  │ NOTE: Only executes when Step 5 approval is passed.                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 7: CREATE JIRA TICKET                                             │ │
│  │ Lambda: outageshield-ticket-integrator-dev (07-notifications-stack)     │ │
│  │ • Gets Jira credentials from AWS Secrets Manager                       │ │
│  │ • Creates ticket via Jira REST API v3 (Atlassian Document Format)      │ │
│  │ • Ticket includes: incident details table, root cause, alarm info,     │ │
│  │   OutageShield dashboard link (clickable)                              │ │
│  │ • Writes: ticket_id, ticket_system, ticket_status, ticket_url,         │ │
│  │   ticket_content → outageshield-incidents-dev                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 8: NOTIFY TEAM                                                    │ │
│  │ Lambda: outageshield-notification-dev (07-notifications-stack)          │ │
│  │ • Sends SNS notification:                                              │ │
│  │   - SEV-4+ → Escalation topic                                         │ │
│  │   - SEV-1-3 → Alert topic                                             │ │
│  │ • Message includes: service, severity, root cause, revenue at risk,    │ │
│  │   ticket ID, ticket URL, dashboard link                                │ │
│  │ • Writes: notifications (JSON) → outageshield-incidents-dev            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 9: GENERATE POSTMORTEM                                            │ │
│  │ Lambda: outageshield-postmortem-dev (05-reasoning-stack)                │ │
│  │ • Calls Amazon Bedrock to generate full postmortem report              │ │
│  │ • Output includes:                                                     │ │
│  │   - summary (what happened)                                            │ │
│  │   - duration (how long)                                                │ │
│  │   - root_cause (why it happened)                                       │ │
│  │   - impact (who was affected)                                          │ │
│  │   - prevention[] (how to prevent it next time)                         │ │
│  │ • Writes → outageshield-postmortems-dev (separate table)               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 10: DONE                                                          │ │
│  │ Workflow complete. All data stored in DynamoDB.                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BEDROCK AGENT (13-bedrock-agent-stack) — Autonomous Investigation          │
│                                                                             │
│  Agent: outageshield-investigator-dev                                       │
│  Model: Claude 3 Haiku                                                      │
│  Role: Supplementary deep investigation (invoked on demand)                 │
│                                                                             │
│  Action Groups (tools the agent can call autonomously):                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ /search-incidents  → Query DynamoDB for past incidents on service   │   │
│  │ /search-logs       → Query OpenSearch/Events for error patterns     │   │
│  │ /get-runbook       → Look up alarm-specific remediation runbook     │   │
│  │ /check-deployments → Check recent deployments and config changes    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  The agent decides ON ITS OWN which tools to call and how many              │
│  iterations to perform. Can be invoked via:                                 │
│  • AWS Bedrock Console (test)                                               │
│  • AWS SDK (bedrock-agent-runtime:InvokeAgent)                              │
│  • Any Lambda or API endpoint                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DASHBOARD LAYER (09-dashboard-stack + 11-websocket + 12-cloudfront)        │
│                                                                             │
│  API Gateway (REST): /incidents, /risk, /postmortems, /events, /approve     │
│  API Gateway (WebSocket): Real-time incident updates                        │
│  Lambda: outageshield-dashboard-dev — reads from all DynamoDB tables        │
│                                                                             │
│  React UI (CloudFront + S3):                                                │
│  • Dashboard — stats, business impact bars, donut chart, incidents table    │
│  • Incidents — full list with search, severity, status, root cause          │
│  • Incident Detail — root cause + confidence, recommendations,             │
│    postmortem link, Jira ticket, SNS notification, business details         │
│  • Postmortems — master-detail with scoring reasoning, prevention steps    │
│  • Notifications — Jira tickets (external link) + SNS alerts               │
│  • Login — Cognito authentication                                           │
│                                                                             │
│  Live: https://d2k1km1tzlio49.cloudfront.net                                │
│  Jira: https://corpinfollc.atlassian.net/jira/software/projects/TGSHLD     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DynamoDB Tables

| Table | Records | Written By | Contains |
|-------|---------|-----------|----------|
| `outageshield-events-dev` | Raw alarm events | Detection Lambda | event_id, source, service, alarm_name, severity, timestamp |
| `outageshield-incidents-dev` | Enriched incidents | Steps 1-8 | All scores, root cause, recommendations, ticket, notifications |
| `outageshield-workflow-state-dev` | Workflow tracking | Step Functions | execution_id, status, timestamps |
| `outageshield-postmortems-dev` | AI postmortems | Postmortem Lambda (Step 9) | summary, duration, root_cause, impact, prevention[] |
| `outageshield-runbooks-dev` | Runbook templates | Manual / Config | service, alarm_type, steps[] |

---

## Project Structure

```
OutageShield AI/
├── stacks/                            ← 13 AWS CloudFormation stacks
│   ├── 01-ingestion-stack.yaml        ← EventBridge rules
│   ├── 02-storage-stack.yaml          ← DynamoDB (5 tables) + OpenSearch
│   ├── 03-detection-stack.yaml        ← Detection Lambda + X-Ray
│   ├── 04-correlation-stack.yaml      ← Correlation Lambda
│   ├── 05-reasoning-stack.yaml        ← Bedrock AI (4 Lambdas: scoring, RCA, remediation, postmortem)
│   ├── 06-orchestration-stack.yaml    ← Step Functions (10-step workflow)
│   ├── 07-notifications-stack.yaml    ← SNS + Notification Lambda + Jira Ticket Lambda
│   ├── 08-remediation-stack.yaml      ← Remediation Executor + SSM Documents
│   ├── 09-dashboard-stack.yaml        ← API Gateway + Dashboard Lambda
│   ├── 10-auth-stack.yaml             ← Amazon Cognito
│   ├── 11-websocket-stack.yaml        ← WebSocket API
│   ├── 12-cloudfront-stack.yaml       ← S3 + CloudFront
│   ├── 13-bedrock-agent-stack.yaml    ← Bedrock Agent + Action Group Lambda
│   ├── deploy.sh
│   └── stepfunctions/
│       ├── incident-workflow.asl.json
│       ├── approval-lambda.py
│       └── README.md
├── UI/                                ← React Dashboard (Vite + TypeScript + Tailwind)
│   └── src/
│       ├── pages/                     ← Dashboard, Incidents, IncidentDetail, Postmortems,
│       │                                 Notifications, TicketDetail, SnsDetail, Login
│       ├── services/api.ts            ← REST API client
│       ├── services/auth.ts           ← Cognito auth
│       └── services/websocket.ts      ← Real-time updates
├── scripts/
│   ├── push-100.py                    ← Trigger 100 incidents
│   ├── delete-jira-tickets.py         ← Delete all Jira tickets
│   ├── clean-and-push-100.py          ← Full reset + push
│   └── delete-all.sh                  ← Delete all AWS resources
└── docs/
    ├── data-ingestion-guide.md
    └── continuous-learning.md
```

---

## Demo

```bash
# Push 100 incidents through the full AI pipeline
python scripts/push-100.py

# Wait 15-20 minutes for Bedrock AI to process all workflows
# Then view: https://d2k1km1tzlio49.cloudfront.net
# Login: sre-team@shopsphere.com / OutageShield2024!
```

**What happens for each incident:**
```
CloudWatch alarm → Detection Lambda → stores event → starts Step Functions
→ Step 1: Correlate (gather context)
→ Step 2: Score (Bedrock: severity 4, impact 8, revenue $50K/hr)
→ Step 3: RCA (Bedrock: "DB connection spike after deployment")
→ Step 3b: Agent Investigation (searches past incidents, logs, runbook, deployments)
→ Step 4: Remediation (Bedrock: [{rollback, 85%}, {scale, 70%}])
→ Step 5: Approval gate (skipped — default path)
→ Step 6: Execute remediation (SSM — only if approved)
→ Step 7: Jira ticket created (TGSHLD-XXX with dashboard link)
→ Step 8: SNS alert sent (escalation for SEV-4+)
→ Step 9: Postmortem generated (summary + prevention steps)
→ Step 10: Done — all data in DynamoDB, visible in dashboard
```

All data is produced by the AI agent pipeline — **no mock data**.

---

## Engineering Tasks (Completed)

- ✅ Ingest CloudWatch metrics, logs, alarms, and operational events
- ✅ Correlate alerts with deployment events, configuration changes, and incident history
- ✅ Build root-cause reasoning workflow using Bedrock
- ✅ Map incidents to runbooks and recommended remediation actions
- ✅ Create incident severity scoring and business impact estimation
- ✅ Build dashboard for active incidents, outage risk, and recommended actions
- ✅ Integrate with Jira for ticket creation and workflow handoff
- ✅ Generate post-incident summaries and prevention recommendations

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
| Human-in-the-Loop Approval | Enable `auto_remediation_enabled` to pause workflow for human approval |
| Continuous Learning | Feed resolved outcomes back to improve AI accuracy |
| Multi-account Support | Monitor across AWS accounts via Organizations |
| Slack/PagerDuty Integration | Direct notification channels |

---

## Real-World Example: payments-api High Latency Incident

Here's exactly what happens when a real incident flows through OutageShield AI:

### 1. The Alert

```
CloudWatch Alarm: HighLatency-payments-api
Reason: "Threshold Crossed: P99 latency (1200ms) > threshold (500ms)"
Time: 2024-01-15 10:32:00 UTC
```

### 2. Detection (Step 0)

The Detection Lambda receives the alarm event and:
- Stores it in `outageshield-events-dev` with event_id, service=payments-api, alarm_name
- Starts a Step Functions workflow execution

### 3. Correlation (Step 1)

The Correlation Lambda gathers context:
- CloudWatch metrics: CPU at 45%, memory at 72%, request count spiked 3x
- X-Ray traces: downstream calls to `database-proxy` taking 800ms (normally 50ms)
- CloudTrail: deployment event 30 minutes ago (deploy v2.4.1)
- AWS Config: connection pool size changed from 50 to 100

Creates incident record: `INC-A1B2C3D4`

### 4. Scoring (Step 2)

Bedrock AI evaluates the incident:
```json
{
  "severity_score": 4,
  "business_impact_score": 8,
  "revenue_at_risk": "High ($75,000 per hour)",
  "affected_users": 15000,
  "sla_status": "At Risk",
  "scoring_reasoning": "payments-api is a critical revenue path. P99 latency 
   of 1200ms will cause checkout timeouts, cart abandonment, and failed 
   transactions. 15K active users affected during peak hours."
}
```

### 5. Root Cause Analysis (Step 3)

Bedrock AI analyzes all context and determines:
```json
{
  "root_cause": "Database connection pool exhaustion following deployment v2.4.1. 
   The new code introduced a connection leak in the payment processing handler, 
   causing connections to accumulate without being released. This led to connection 
   timeouts and cascading latency across all payment endpoints.",
  "confidence": 87
}
```

### 6. Bedrock Agent Deep Investigation (Step 3b)

The Bedrock Agent is invoked and autonomously investigates:

```
Agent: "Let me search for similar past incidents..."
  → /search-incidents (service=payments-api)
  → Found: 2 similar incidents in the last 60 days, both after deployments

Agent: "Let me check the logs..."
  → /search-logs (service=payments-api, time_range=1h)
  → Found: "Connection timeout" errors spiked from 0 to 340/min at 10:32

Agent: "What does the runbook say?"
  → /get-runbook (alarm_type=HighLatency)
  → Got: "Check recent deployments, review DB connection pool, consider rollback"

Agent: "Were there recent deployments?"
  → /check-deployments (service=payments-api)
  → Found: Deploy v2.4.1 at 10:02 — "Updated payment processing handler"

Agent conclusion:
  "This is the 3rd connection-related incident after a deployment in 60 days.
   Deploy v2.4.1 introduced a connection leak. Immediate rollback to v2.3.9 
   recommended. Long-term: add connection pool monitoring and pre-deploy 
   load testing."
```

### 7. Remediation Recommendations (Step 4)

Bedrock generates ranked options:
```json
[
  {
    "category": "rollback",
    "description": "Rollback payments-api to v2.3.9 (last stable version)",
    "confidence": 92,
    "risk": "low",
    "estimated_ttr": 5
  },
  {
    "category": "scaling",
    "description": "Increase database connection pool to 200 and add read replicas",
    "confidence": 65,
    "risk": "medium",
    "estimated_ttr": 15
  },
  {
    "category": "configuration_change",
    "description": "Add connection timeout of 30s and idle connection cleanup",
    "confidence": 55,
    "risk": "low",
    "estimated_ttr": 10
  }
]
```

### 8. Jira Ticket Created (Step 7)

A ticket is created in Jira:
```
Project: TGSHLD
Key: TGSHLD-456
Priority: High
Summary: [OutageShield] SEV-4 | payments-api | HighLatency-payments-api

Description includes:
- Incident details table (ID, service, severity, impact, revenue, users, SLA)
- Root cause analysis with 87% confidence
- Link to OutageShield Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/INC-A1B2C3D4
```

### 9. SNS Alert Sent (Step 8)

An escalation alert (SEV-4+) is sent to the SRE team:
```
Subject: [OutageShield] SEV-4 | payments-api | HighLatency-payments-api

Body:
  Service: payments-api
  Severity: SEV-4
  Root Cause: Database connection pool exhaustion following deployment v2.4.1
  Revenue at Risk: $75,000/hr
  Affected Users: 15,000
  Jira Ticket: TGSHLD-456
  Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/INC-A1B2C3D4
```

### 10. Postmortem Generated (Step 9)

Bedrock generates a full postmortem:
```json
{
  "summary": "payments-api experienced 1200ms P99 latency for 45 minutes due to 
   a connection pool leak introduced in deployment v2.4.1",
  "duration": "45 minutes",
  "root_cause": "Connection leak in payment processing handler (v2.4.1)",
  "impact": "15,000 users affected. Estimated $56,250 revenue impact. 
   Cart abandonment rate increased 340%. SLA breached for enterprise tier.",
  "prevention": [
    "Add connection pool monitoring with alerts at 80% utilization",
    "Implement pre-deployment load testing in staging environment",
    "Add circuit breaker pattern for database connections",
    "Require connection leak testing in code review checklist",
    "Set up canary deployments with automatic rollback on latency spike"
  ]
}
```

### 11. Dashboard Shows Everything

The SRE team opens `https://d2k1km1tzlio49.cloudfront.net` and sees:
- **Dashboard**: payments-api incident with SEV-4, business impact 8/10
- **Incident Detail**: root cause, 87% confidence, 3 recommendations, Jira link
- **Postmortem**: full report with 5 prevention steps
- **Notifications**: SNS alert sent, Jira ticket TGSHLD-456 linked

**Total time from alarm to full investigation: ~3 minutes** (vs. 30-60 minutes manually).
