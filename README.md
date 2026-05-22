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

---

## AWS Services

| Service | Role |
|---------|------|
| Amazon CloudWatch | Metrics, logs, and alarms ingestion |
| AWS X-Ray | Application tracing (active on all Lambdas + Step Functions) |
| AWS CloudTrail | API activity and change tracking |
| AWS Config | Configuration state and drift detection |
| Amazon EventBridge | Event routing and incident triggers |
| AWS Lambda | 10+ functions across the pipeline |
| AWS Step Functions | 10-step incident workflow orchestration |
| Amazon Bedrock | Claude 3 Haiku — scoring, RCA, remediation, postmortem |
| Amazon Bedrock Agents | Autonomous investigation (searches incidents, logs, runbooks, deployments) |
| Amazon DynamoDB | 5 tables: events, incidents, runbooks, workflow-state, postmortems |
| Amazon OpenSearch Serverless | Log indexing, search, and incident correlation |
| AWS Systems Manager | Execute remediation (rollback, scale, config) via SSM Documents |
| Amazon SNS | Multi-channel notifications (alert + escalation) |
| Amazon Cognito | User authentication |
| API Gateway (REST + WebSocket) | Dashboard API + real-time streaming |
| Amazon S3 + CloudFront | UI hosting (CDN, HTTPS, SPA) |
| Jira Cloud | Ticket creation via REST API v3 |

---

## End-to-End Pipeline with Reasoning

```
Step 0: DETECT → Step 1: CORRELATE → Step 2: SCORE → Step 3: RCA
→ Step 3b: AGENT INVESTIGATION → Step 4: REMEDIATION → Step 5: APPROVAL
→ Step 6: EXECUTE → Step 7: TICKET → Step 8: NOTIFY → Step 9: POSTMORTEM → DONE
```

### How Data Flows Between Steps (with reasoning chain)

```
Step 3 (RCA) outputs root_cause + confidence
       │
       ▼ feeds into
Step 3b (Agent) uses root_cause to guide autonomous investigation
       │ searches: past incidents, logs, runbooks, deployments
       ▼ feeds into
Step 4 (Remediation) uses BOTH root_cause AND agent findings
       │ generates evidence-based recommendations with reasoning
       ▼
Steps 7-9 use all accumulated data for ticket, alert, postmortem
```

---

## Real-World Example: Full Reasoning Flow

### Scenario: `HighLatency-payments-api`

A CloudWatch alarm fires because payments-api P99 latency exceeded 500ms.

---

### Step 0: DETECTION

```
INPUT:  CloudWatch alarm event
        alarmName: "HighLatency-payments-api"
        reason: "Threshold Crossed: P99 latency (1200ms) > threshold (500ms)"

ACTION: Detection Lambda receives alarm
        → Stores event in DynamoDB (outageshield-events-dev)
        → Indexes event in OpenSearch Serverless (outageshield-logs index)
        → Starts Step Functions workflow

OUTPUT: signal = {
          signal_id: "INC-A1B2C3D4",
          service: "payments-api",
          detection_type: "metric",
          severity_score: 4
        }
```

---

### Step 1: CORRELATE

```
INPUT:  signal from Step 0

ACTION: Correlation Lambda gathers context:
        → CloudWatch metrics: CPU 45%, memory 72%, requests 3x normal
        → X-Ray traces: downstream calls to database-proxy taking 800ms
        → CloudTrail: deployment event 30 min ago (deploy v2.4.1)
        → AWS Config: connection pool size changed from 50 to 100

OUTPUT: Creates incident record in outageshield-incidents-dev
        incident_context = {
          service: "payments-api",
          metrics: {cpu: 45, memory: 72, request_spike: "3x"},
          traces: {slow_dependency: "database-proxy", latency: "800ms"},
          recent_deployment: "v2.4.1 (30 min ago)",
          config_change: "max_connections: 50 → 100"
        }
```

---

### Step 2: SCORE

```
INPUT:  signal + incident_context from Step 1

ACTION: Scoring Lambda calls Bedrock with all context
        PROMPT: "Evaluate severity and business impact for payments-api
                 with 1200ms latency, 3x request spike, recent deployment..."

BEDROCK REASONING:
        "payments-api is a critical revenue path. P99 latency of 1200ms
         will cause checkout timeouts and cart abandonment. With 3x request
         spike during peak hours, approximately 15,000 users are affected.
         Revenue impact estimated at $75K/hr based on average transaction
         value and current traffic volume."

OUTPUT: {
          severity_score: 4,
          business_impact_score: 8,
          revenue_at_risk: "High ($75,000 per hour)",
          affected_users: 15000,
          sla_status: "At Risk",
          scoring_reasoning: "Critical revenue path, peak hours, 15K users..."
        }
        → Written to outageshield-incidents-dev
```

---

### Step 3: ROOT CAUSE ANALYSIS

```
INPUT:  signal + step1 context + step2 scores

ACTION: RCA Lambda calls Bedrock with full context
        PROMPT: "Analyze root cause. Service: payments-api. Latency: 1200ms.
                 Recent deploy: v2.4.1. DB proxy latency: 800ms.
                 Config change: connection pool 50→100..."

BEDROCK REASONING:
        "The latency spike correlates with deployment v2.4.1 (30 min ago).
         X-Ray shows database-proxy calls went from 50ms to 800ms.
         The connection pool config change (50→100) suggests awareness of
         connection issues, but the deployment likely introduced a connection
         leak in the payment processing handler, causing pool exhaustion
         despite the increased limit."

OUTPUT: {
          root_causes: [{
            description: "Database connection pool exhaustion caused by
                         connection leak in deployment v2.4.1",
            confidence: 87
          }]
        }
        → Written to outageshield-incidents-dev (root_cause, confidence)
```

---

### Step 3b: BEDROCK AGENT DEEP INVESTIGATION

```
INPUT:  signal + step3.root_causes (feeds from Step 3)

ACTION: Agent Invoker Lambda calls Bedrock Agent with:
        "Investigate payments-api. Root cause suggests: DB connection pool
         exhaustion from v2.4.1. Search past incidents, logs, runbook, deployments."

AGENT AUTONOMOUS REASONING:
        Agent thinks: "Let me search for similar past incidents..."
        → Calls /search-incidents (service=payments-api)
        → DynamoDB returns: 2 similar incidents in last 60 days, both post-deploy

        Agent thinks: "Let me check the logs for patterns..."
        → Calls /search-logs (service=payments-api, time_range=1h)
        → OpenSearch returns: "Connection timeout" errors spiked 0→340/min at 10:32

        Agent thinks: "What does the runbook say for this alarm type?"
        → Calls /get-runbook (alarm_type=HighLatency)
        → DynamoDB runbooks table returns: "Check deployments, review DB pool,
           consider rollback if post-deploy"

        Agent thinks: "Were there recent deployments?"
        → Calls /check-deployments (service=payments-api)
        → Returns: Deploy v2.4.1 at 10:02 — "Updated payment processing handler"

AGENT CONCLUSION:
        "This is the 3rd connection-related incident after a deployment in 60 days.
         Deploy v2.4.1 introduced a connection leak (340 timeout errors/min).
         Runbook recommends rollback. Past incidents resolved by rollback within 5 min."

OUTPUT: {
          investigation: "3rd similar incident. Deploy v2.4.1 caused connection
                         leak. 340 timeout errors/min. Runbook: rollback.
                         Past resolution: rollback in 5 min.",
          status: "completed"
        }
        → Written to outageshield-incidents-dev (agent_investigation)
```

---

### Step 4: REMEDIATION RECOMMENDATIONS

```
INPUT:  step3.root_causes + step3b.investigation (feeds from BOTH Step 3 and 3b)

ACTION: Remediation Lambda calls Bedrock with:
        - Root cause from Step 3
        - Agent investigation from Step 3b
        - Anti-hallucination instructions: "Only recommend actions supported
          by the evidence. Cite specific findings. Do not invent information."

BEDROCK REASONING (evidence-based):
        "Based on evidence:
         1. Agent found 3 similar incidents resolved by rollback (EVIDENCE: past incidents)
         2. Connection timeout errors at 340/min (EVIDENCE: OpenSearch logs)
         3. Runbook says rollback for post-deploy latency (EVIDENCE: runbook)
         4. Deploy v2.4.1 correlates with incident start (EVIDENCE: deployment check)

         Recommendations ranked by evidence strength:"

OUTPUT: [
          {
            category: "rollback",
            description: "Rollback payments-api to v2.3.9",
            reasoning: "3 past incidents resolved by rollback. Deploy v2.4.1
                       correlates with 340 timeout errors/min starting at 10:32.",
            effectiveness: 5,
            risk: "low",
            estimated_ttr_minutes: 5,
            confidence: 92,
            evidence: "Past incidents + deployment correlation + runbook"
          },
          {
            category: "scaling",
            description: "Increase DB connection pool to 200 + add read replicas",
            reasoning: "Connection pool exhaustion confirmed. May reduce symptoms
                       but won't fix the leak in v2.4.1 code.",
            effectiveness: 3,
            risk: "medium",
            estimated_ttr_minutes: 15,
            confidence: 65,
            evidence: "Connection timeout pattern in logs"
          },
          {
            category: "configuration_change",
            description: "Add connection timeout of 30s + idle cleanup",
            reasoning: "Would prevent pool exhaustion but is a workaround,
                       not a fix for the underlying leak.",
            effectiveness: 2,
            risk: "low",
            estimated_ttr_minutes: 10,
            confidence: 55,
            evidence: "Runbook recommendation for connection issues"
          }
        ]
        → Written to outageshield-incidents-dev (recommendations_raw)
```

---

### Step 7: JIRA TICKET

```
INPUT:  All accumulated data (scores, root cause, agent findings, recommendations)

ACTION: Ticket Lambda creates Jira ticket via REST API v3

OUTPUT: TGSHLD-456 created with:
        - Incident details table (ID, service, severity, impact, revenue, users)
        - Root cause with 87% confidence
        - Dashboard link: https://d2k1km1tzlio49.cloudfront.net/incidents/INC-A1B2C3D4
```

---

### Step 8: SNS NOTIFY

```
INPUT:  All data + ticket info

ACTION: Sends escalation alert (SEV-4+)

OUTPUT: Email to sre-team with:
        Service: payments-api | SEV-4 | Revenue: $75K/hr
        Root Cause: DB connection pool exhaustion (v2.4.1)
        Ticket: TGSHLD-456
        Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/INC-A1B2C3D4
```

---

### Step 9: POSTMORTEM

```
INPUT:  All data from Steps 1-8

ACTION: Postmortem Lambda calls Bedrock to generate full report

OUTPUT: {
          summary: "payments-api 1200ms P99 latency for 45 min due to
                   connection pool leak in v2.4.1",
          duration: "45 minutes",
          root_cause: "Connection leak in payment processing handler (v2.4.1)",
          impact: "15,000 users. $56,250 revenue impact. SLA breached.",
          prevention: [
            "Add connection pool monitoring with alerts at 80% utilization",
            "Implement pre-deployment load testing in staging",
            "Add circuit breaker pattern for database connections",
            "Require connection leak testing in code review checklist",
            "Set up canary deployments with automatic rollback on latency spike"
          ]
        }
        → Written to outageshield-postmortems-dev
```

---

### Dashboard Shows Everything

The SRE opens `https://d2k1km1tzlio49.cloudfront.net`:
- **Dashboard**: payments-api SEV-4, impact 8/10, revenue $75K/hr at risk
- **Incident Detail**: root cause (87% confidence), 3 evidence-based recommendations, Jira link
- **Postmortem**: full report with 5 prevention steps
- **Notifications**: SNS alert sent, TGSHLD-456 linked

**Total time from alarm to full investigation with recommendations: ~3 minutes**

---

## Project Structure

```
OutageShield AI/
├── stacks/                         ← 13 CloudFormation stacks
│   ├── 01-ingestion-stack.yaml     ← EventBridge
│   ├── 02-storage-stack.yaml       ← DynamoDB (5 tables) + OpenSearch Serverless
│   ├── 03-detection-stack.yaml     ← Detection Lambda + OpenSearch indexing
│   ├── 04-correlation-stack.yaml   ← Correlation Lambda
│   ├── 05-reasoning-stack.yaml     ← Bedrock AI (scoring, RCA, remediation, postmortem)
│   ├── 06-orchestration-stack.yaml ← Step Functions (10-step + Step 3b)
│   ├── 07-notifications-stack.yaml ← SNS + Jira Ticket Lambda
│   ├── 08-remediation-stack.yaml   ← SSM Executor + Documents
│   ├── 09-dashboard-stack.yaml     ← API Gateway + Dashboard Lambda
│   ├── 10-auth-stack.yaml          ← Cognito
│   ├── 11-websocket-stack.yaml     ← WebSocket API
│   ├── 12-cloudfront-stack.yaml    ← S3 + CloudFront
│   └── 13-bedrock-agent-stack.yaml ← Bedrock Agent + Action Groups + Invoker
├── UI/                             ← React Dashboard (Vite + TypeScript + Tailwind)
├── scripts/                        ← Demo and utility scripts
└── docs/                           ← Documentation
```

---

## Demo

```bash
python scripts/push-100.py          # Trigger 100 incidents
# Wait 15-20 min for Bedrock AI
# View: https://d2k1km1tzlio49.cloudfront.net
# Login: sre-team@shopsphere.com / OutageShield2024!
```

---

## Engineering Tasks ✅

- ✅ Ingest CloudWatch metrics, logs, alarms, and operational events
- ✅ Correlate alerts with deployment events, configuration changes, and incident history
- ✅ Build root-cause reasoning workflow using Bedrock
- ✅ Map incidents to runbooks and recommended remediation actions
- ✅ Create incident severity scoring and business impact estimation
- ✅ Build dashboard for active incidents, outage risk, and recommended actions
- ✅ Integrate with Jira for ticket creation and workflow handoff
- ✅ Generate post-incident summaries and prevention recommendations

## Definition of Done ✅

- ✅ Agent detects and correlates alerts, logs, telemetry, and changes
- ✅ Agent identifies likely root cause and recommends remediation steps
- ✅ User can view outage risk, business impact, and incident status in dashboard
- ✅ System can create tickets and generate incident/postmortem summaries
- ✅ System runs on AWS using CloudWatch, X-Ray, CloudTrail, Config, OpenSearch, Bedrock, Bedrock Agents, Lambda, Step Functions, EventBridge, DynamoDB, Systems Manager, SNS, and Jira
