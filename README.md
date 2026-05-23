# OutageShield AI

AI-powered incident detection, correlation, root-cause analysis, and automated remediation platform for enterprise cloud operations. Built on AWS with Amazon Bedrock (Claude 3) as the reasoning engine and a Bedrock Agent for autonomous investigation.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          OutageShield AI — Data Flow                                  │
│                                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────────┐  │
│  │  CloudWatch  │────▶│  EventBridge │────▶│  Ingestion   │────▶│   Detection   │  │
│  │   Alarms     │     │              │     │   Lambda     │     │    Lambda     │  │
│  │  CloudTrail  │     │  (Rules)     │     │ (Normalize)  │     │ (Threshold)   │  │
│  │  AWS Config  │     │              │     │              │     │              │  │
│  └──────────────┘     └──────────────┘     └──────────────┘     └──────┬────────┘  │
│                                                                         │           │
│                                              ┌──────────────────────────┼──────┐    │
│                                              │         Writes to:       │      │    │
│                                              │  • DynamoDB Events Table ▼      │    │
│                                              │  • OpenSearch Serverless        │    │
│                                              │  • Starts Step Functions ───────┘    │
│                                              └─────────────────────────────────┘    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                    Step Functions — 9-Step Workflow                           │    │
│  │                                                                             │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │    │
│  │  │1.Correlate│─▶│2.Score  │─▶│3.RCA    │─▶│3b.Agent │─▶│4.Remediation    │  │    │
│  │  │(Context) │  │(Bedrock)│  │(Bedrock)│  │(Bedrock │  │(Bedrock)        │  │    │
│  │  │          │  │         │  │         │  │ Agent)  │  │Anti-hallucinate │  │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └────────┬────────┘  │    │
│  │                                                                  │          │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │          │    │
│  │  │5.Approve│─▶│6.Execute│─▶│7.Ticket │─▶│8.Notify │─▶─────────┘          │    │
│  │  │(Human)  │  │(SSM)    │  │(Jira)   │  │(SNS)    │                      │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  ┌─────────┐        │    │
│  │                                                         │9.Post-  │        │    │
│  │                                                         │ mortem  │        │    │
│  │                                                         │(Bedrock)│        │    │
│  │                                                         └─────────┘        │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Real-Time Dashboard                                  │    │
│  │                                                                             │    │
│  │  DynamoDB ──▶ WebSocket API ──▶ React UI (CloudFront)                       │    │
│  │  Streams       (push updates)    • Incidents list                           │    │
│  │                                  • Root cause + confidence                  │    │
│  │                                  • Recommendations with sources             │    │
│  │                                  • Agent investigation                      │    │
│  │                                  • Jira ticket + SNS notification           │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## AWS Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account (us-east-1)                                  │
│                                                                                     │
│  ┌─── Ingestion ───────────────────────────────────────────────────────────────┐    │
│  │  Amazon EventBridge (default bus)                                            │    │
│  │    Rules: aws.cloudwatch, aws.cloudtrail, aws.config                        │    │
│  │           ↓                                                                 │    │
│  │  Lambda: outageshield-detection-dev                                         │    │
│  │    + Lambda Layer: opensearch-py                                            │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Storage ─────────────────────────────────────────────────────────────────┐    │
│  │  DynamoDB Tables:                                                            │    │
│  │    • outageshield-incidents-dev (incident records + AI analysis)             │    │
│  │    • outageshield-events-dev (detection events)                             │    │
│  │    • outageshield-postmortems-dev (AI postmortem reports)                   │    │
│  │    • outageshield-runbooks-dev (remediation procedures)                     │    │
│  │                                                                             │    │
│  │  OpenSearch Serverless:                                                      │    │
│  │    • Collection: outageshield-logs-dev (SEARCH type)                        │    │
│  │    • Index: outageshield-logs (alarm events for agent search)               │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── AI / Reasoning ─────────────────────────────────────────────────────────┐    │
│  │  Amazon Bedrock (Claude 3 Haiku):                                           │    │
│  │    • outageshield-rootcause-dev (RCA with confidence scores)                │    │
│  │    • outageshield-scoring-dev (severity + business impact)                  │    │
│  │    • outageshield-remediation-recommend-dev (anti-hallucination)            │    │
│  │    • outageshield-postmortem-dev (uses all previous steps)                  │    │
│  │                                                                             │    │
│  │  Bedrock Agent: outageshield-investigator-dev                               │    │
│  │    • Action Group: IncidentInvestigationTools                               │    │
│  │    • Lambda: outageshield-agent-actions-dev (+ opensearch-py layer)         │    │
│  │    • Tools: searchIncidents, searchLogs, getRunbook, checkDeployments       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Orchestration ──────────────────────────────────────────────────────────┐    │
│  │  AWS Step Functions: outageshield-workflow-dev                               │    │
│  │    9 steps, 32s average execution, retries + error handling                 │    │
│  │    Each step writes progress to DynamoDB                                    │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Notifications ──────────────────────────────────────────────────────────┐    │
│  │  Amazon SNS: escalation alerts (email, Slack, PagerDuty)                    │    │
│  │  Jira Cloud API: auto-create tickets with full context                      │    │
│  │  AWS Systems Manager: execute rollback/scale/config changes                 │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Frontend ───────────────────────────────────────────────────────────────┐    │
│  │  CloudFront + S3: React SPA hosting                                         │    │
│  │  API Gateway (REST): /incidents, /risk, /postmortems, /events              │    │
│  │  API Gateway (WebSocket): real-time push to browser                         │    │
│  │  Amazon Cognito: user authentication                                        │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step Functions Workflow Detail

```
Step 1: Correlate (120s timeout, 2 retries)
    │   Creates incident record, gathers deployments + config changes
    ▼
Step 2: Score (60s timeout, 5 retries)
    │   Bedrock: severity 1-5, business impact 1-10, affected users, revenue
    ▼
Step 3: Root Cause Analysis (120s timeout, 5 retries)
    │   Bedrock: ranked causes with confidence %, bulletproof text extraction
    ▼
Step 3b: Agent Investigation (120s timeout, 2 retries)
    │   Bedrock Agent: searches OpenSearch, past incidents, runbooks, deployments
    │   Excludes current incident from results
    ▼
Step 4: Remediation (120s timeout, 5 retries)
    │   Bedrock: evidence-based recommendations with source attribution
    │   Stores recommendations_raw in DynamoDB
    ▼
Step 5: Approval Gate
    │   If auto_remediation: .waitForTaskToken (human approval)
    ▼
Step 6: Execute (300s timeout, 2 retries)
    │   AWS Systems Manager: rollback / scale / config change
    ▼
Step 7: Jira Ticket (60s timeout, 3 retries)
    │   Creates ticket with root cause, severity, dashboard link
    ▼
Step 8: SNS Notification (30s timeout, 3 retries)
    │   Escalation alert to sre-team with full context
    ▼
Step 9: Postmortem (120s timeout, 5 retries)
    │   Bedrock: uses ALL previous steps, root cause matches Step 3
    ▼
Done (workflow_status: completed)
```

---

## Real Example: Incident on payments-api

**Trigger:** CloudWatch alarm `HighLatency-payments-api` (P99 latency 850ms > 500ms)

**AI Scoring:**
- Severity: 4/5 | Business Impact: 8/10
- Affected Users: 1,000,000 | Revenue at Risk: $10K/min
- SLA Status: At Risk

**Root Cause:** "High API latency due to increased request volume" (80% confidence)

**Agent Investigation:**
- Found 2 similar past incidents on the api service
- OpenSearch logs show HighLatency alarm triggered
- Runbook found for HighLatency alarm (general steps)
- Deployment correlation: recent config change increased max_connections

**Recommendations (evidence-based, no hallucination):**
1. ⚙️ Configuration change — adjust connection pool settings (source: `AGENT:log_patterns`, 80%)
2. ⚙️ Configuration change — implement rate limiting (source: `AGENT:runbook`, 80%)
3. 👤 Manual intervention — update runbook (source: `AGENT:runbook`, 80%)
4. 📈 Scaling — scale up resources (source: `RCA`, 70%)

**Auto-created:** Jira ticket TGSHLD-1474 + SNS escalation to sre-team@shopsphere.com

---

## Architecture

13 CloudFormation stacks, fully serverless:

| # | Stack | Services | Purpose |
|---|-------|----------|---------|
| 01 | Ingestion | EventBridge, Lambda | Collect + normalize events |
| 02 | Storage | DynamoDB, OpenSearch Serverless | Events, incidents, runbooks, postmortems |
| 03 | Detection | Lambda | Threshold evaluation, starts workflow |
| 04 | Correlation | Lambda | Build incident context |
| 05 | Reasoning | Bedrock (Claude 3), Lambda ×4 | RCA, remediation, scoring, postmortem |
| 06 | Orchestration | Step Functions | 9-step workflow |
| 07 | Notifications | SNS, Lambda | Alerts + Jira tickets |
| 08 | Remediation | Lambda, SSM | Execute fixes via Systems Manager |
| 09 | Dashboard | API Gateway, Lambda | REST API |
| 10 | Auth | Cognito | User pool |
| 11 | WebSocket | API Gateway WebSocket | Real-time push |
| 12 | CloudFront | S3, CloudFront | UI hosting |
| 13 | Bedrock Agent | Bedrock Agent, Lambda | Autonomous investigator |

---

## Bedrock Agent — Autonomous Investigator

The agent uses 4 tools to investigate each incident:

| Tool | Data Source | What It Does |
|------|-------------|-------------|
| `searchIncidentHistory` | DynamoDB | Find past incidents on same service |
| `searchLogs` | OpenSearch Serverless | Search alarm patterns, error messages |
| `getRunbook` | DynamoDB | Look up remediation procedures |
| `checkDeployments` | Deployment history | Find recent changes |

**Key behaviors:**
- Excludes the current incident from search results (no self-reference)
- OpenSearch primary → DynamoDB fallback for log search
- Results feed into the Remediation Lambda as evidence

---

## Anti-Hallucination Design

The Remediation Lambda enforces strict rules:
- Only recommends actions supported by evidence from RCA or Agent
- Every recommendation must cite its source: `RCA`, `AGENT:runbook`, `AGENT:past_incidents`, `AGENT:deployment_correlation`, `AGENT:log_patterns`
- Confidence 90%+ requires runbook match or 3+ past incidents
- Falls back to `manual_intervention` with `insufficient_evidence` when data is lacking

---

## Dashboard UI

**Live:** https://d2k1km1tzlio49.cloudfront.net

React 18 + TypeScript + Vite + Tailwind CSS

- **Dashboard** — active incidents, service risk, business impact
- **Incident Detail** — root cause, recommendations with source badges, agent investigation, Jira ticket, SNS notification
- **Postmortems** — AI-generated reports linked to incidents
- **Real-time** — WebSocket push from DynamoDB Streams

---

## Getting Started

### Deploy Infrastructure
```bash
cd stacks
chmod +x deploy.sh
./deploy.sh dev us-east-1
```

### Update Lambda Code
```bash
python scripts/update-rca-lambda-v2.py
python scripts/update-remediation-lambda2.py
python scripts/update-postmortem-lambda.py
python scripts/update-detection-opensearch.py
python scripts/fix-agent-actions.py
python scripts/rebuild-layer.py
```

### Run the UI
```bash
cd UI
npm install
npm run dev
```

### Push Test Data
```bash
# Clear all + push 100 fresh incidents
python scripts/clear-and-push.py

# Push 30 more
python scripts/push-30.py

# Test single incident with full trace
python scripts/test-single-incident.py
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `clear-and-push.py` | Delete tickets + DB (keep runbooks) + push 100 |
| `push-100.py` | Push 100 incidents |
| `push-30.py` | Push 30 incidents |
| `test-single-incident.py` | Full pipeline trace for one incident |
| `get-sample-incident.py` | Inspect a DynamoDB incident record |
| `update-rca-lambda-v2.py` | Deploy RCA Lambda (bulletproof parsing) |
| `update-remediation-lambda2.py` | Deploy Remediation Lambda (anti-hallucination) |
| `update-postmortem-lambda.py` | Deploy Postmortem Lambda (uses all steps) |
| `update-detection-opensearch.py` | Deploy Detection Lambda (opensearch-py) |
| `fix-agent-actions.py` | Deploy Agent Actions Lambda (opensearch-py, excludes self) |
| `rebuild-layer.py` | Rebuild opensearch-py Lambda Layer |
| `create-fresh-opensearch.py` | Create OpenSearch collection + policies |
| `run-demo.sh` | Push EventBridge test events |
| `delete-all.sh` | Delete all CloudFormation stacks |

---

## Data Storage

| Table | Key | Content |
|-------|-----|---------|
| `outageshield-incidents-dev` | `incident_id` | Full incident records with AI analysis |
| `outageshield-events-dev` | `event_id` | Detection events (alarms) |
| `outageshield-postmortems-dev` | `postmortem_id` | AI postmortem reports |
| `outageshield-runbooks-dev` | `runbook_id` | Remediation procedures (15 items) |

**OpenSearch Serverless:**
- Collection: `outageshield-logs-dev`
- Index: `outageshield-logs`
- Stores: alarm events with service, severity, alarm_name, reason, timestamp

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI | Amazon Bedrock (Claude 3 Haiku), Bedrock Agents |
| Orchestration | AWS Step Functions |
| Compute | AWS Lambda (Python 3.12) + opensearch-py Layer |
| Storage | DynamoDB, OpenSearch Serverless |
| Ingestion | Amazon EventBridge |
| Notifications | Amazon SNS, Jira Cloud API |
| Remediation | AWS Systems Manager |
| Auth | Amazon Cognito |
| Real-time | API Gateway WebSocket |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Hosting | S3 + CloudFront |
| IaC | AWS CloudFormation (13 stacks) |
