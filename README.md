# OutageShield AI

AI-powered incident detection, root-cause analysis, autonomous investigation, and automated remediation for enterprise cloud operations. Built on AWS with Amazon Bedrock (Claude 3 Haiku) as the reasoning engine and a Bedrock Agent for autonomous investigation.

**Live Dashboard:** https://d2k1km1tzlio49.cloudfront.net

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          OutageShield AI — End-to-End Data Flow                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  INGESTION LAYER                                                              │   │
│  │                                                                              │   │
│  │  CloudWatch Alarms ──┐                                                       │   │
│  │  CloudTrail Events   ├──▶  Amazon EventBridge  ──▶  Detection Lambda        │   │
│  │  AWS Config Changes  ┘     (default bus, rules)      • Extracts service name │   │
│  │                                                       • Calculates severity  │   │
│  │                                                       • Writes to DynamoDB   │   │
│  │                                                       • Indexes to OpenSearch│   │
│  │                                                       • Starts Step Functions│   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  ORCHESTRATION LAYER — Step Functions Workflow (9 steps, ~40s avg)           │   │
│  │                                                                              │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────────┐  │   │
│  │  │ Step 1   │   │ Step 2   │   │ Step 3   │   │ Step 3b                  │  │   │
│  │  │Correlate │──▶│  Score   │──▶│   RCA    │──▶│  Bedrock Agent           │  │   │
│  │  │          │   │          │   │          │   │  Autonomous Investigation │  │   │
│  │  │• Context │   │• Severity│   │• 3 causes│   │  • Search past incidents  │  │   │
│  │  │• History │   │• Revenue │   │• Confid. │   │  • Query OpenSearch logs  │  │   │
│  │  │• Deploys │   │• Users   │   │• Evidence│   │  • Look up runbooks       │  │   │
│  │  │          │   │• SLA     │   │          │   │  • Check deployments      │  │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────────────────────┘  │   │
│  │                                                            │                  │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┴───────────────┐  │   │
│  │  │ Step 9   │   │ Step 8   │   │ Step 7   │   │ Step 4                   │  │   │
│  │  │Postmortem│◀──│  Notify  │◀──│  Ticket  │◀──│  Remediation             │  │   │
│  │  │          │   │          │   │          │   │  • Evidence-based recs   │  │   │
│  │  │• Summary │   │• SNS     │   │• Jira    │   │  • Source attribution    │  │   │
│  │  │• Root    │   │• Email   │   │• Auto-   │   │  • Anti-hallucination    │  │   │
│  │  │  cause   │   │• Slack   │   │  create  │   │  • Smart injection       │  │   │
│  │  │• Prevent │   │          │   │          │   └──────────────────────────┘  │   │
│  │  └──────────┘   └──────────┘   └──────────┘            │                   │   │
│  │                                                          ▼                   │   │
│  │                                              ┌──────────────────────────┐    │   │
│  │                                              │ Step 5: Approval Gate    │    │   │
│  │                                              │ (human-in-the-loop)      │    │   │
│  │                                              │         │                │    │   │
│  │                                              │         ▼                │    │   │
│  │                                              │ Step 6: Execute (SSM)    │    │   │
│  │                                              │ • Rollback deployment    │    │   │
│  │                                              │ • Scale resources        │    │   │
│  │                                              │ • Config change          │    │   │
│  │                                              └──────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  STORAGE LAYER                                                                │   │
│  │                                                                              │   │
│  │  DynamoDB                          OpenSearch Serverless                     │   │
│  │  ├── outageshield-incidents-dev    └── outageshield-logs (alarm events)      │   │
│  │  ├── outageshield-events-dev                                                 │   │
│  │  ├── outageshield-postmortems-dev                                            │   │
│  │  └── outageshield-runbooks-dev                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                              DynamoDB Streams                                       │
│                                          │                                          │
│                                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  PRESENTATION LAYER                                                           │   │
│  │                                                                              │   │
│  │  API Gateway (REST)  ──▶  Lambda  ──▶  DynamoDB                             │   │
│  │  /incidents, /risk, /postmortems, /events, /approve                         │   │
│  │                                                                              │   │
│  │  API Gateway (WebSocket)  ──▶  Lambda  ──▶  DynamoDB Streams                │   │
│  │  Real-time push to connected browsers                                        │   │
│  │                                                                              │   │
│  │  CloudFront + S3  ──▶  React SPA (TypeScript + Vite + Tailwind)             │   │
│  │  https://d2k1km1tzlio49.cloudfront.net                                      │   │
│  │                                                                              │   │
│  │  Amazon Cognito  ──▶  User authentication                                   │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## AWS Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account (us-east-1)                                  │
│                                                                                     │
│  ┌─── Stack 01-03: Ingestion + Storage + Detection ───────────────────────────┐    │
│  │                                                                             │    │
│  │  EventBridge ──▶ Lambda: outageshield-detection-dev                        │    │
│  │                    │  + Layer: opensearch-py                                │    │
│  │                    ├──▶ DynamoDB: outageshield-events-dev                  │    │
│  │                    ├──▶ OpenSearch: outageshield-logs (SEARCH collection)  │    │
│  │                    └──▶ Step Functions: outageshield-workflow-dev           │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Stack 04-05: Correlation + Reasoning ───────────────────────────────────┐    │
│  │                                                                             │    │
│  │  Lambda: outageshield-correlate-dev                                         │    │
│  │                                                                             │    │
│  │  Bedrock (Claude 3 Haiku) via Lambda:                                       │    │
│  │    outageshield-scoring-dev          → severity, revenue, SLA              │    │
│  │    outageshield-rootcause-dev        → 3 causes, confidence, evidence      │    │
│  │    outageshield-remediation-recommend-dev → source-attributed recs         │    │
│  │    outageshield-postmortem-dev       → summary, prevention, impact         │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Stack 13: Bedrock Agent ─────────────────────────────────────────────────┐    │
│  │                                                                             │    │
│  │  Bedrock Agent: outageshield-investigator-dev                               │    │
│  │    Model: Claude 3 Haiku                                                    │    │
│  │    Action Group: IncidentInvestigationTools                                 │    │
│  │                                                                             │    │
│  │  Lambda: outageshield-agent-actions-dev (+ opensearch-py layer)             │    │
│  │    /search-incidents  → DynamoDB scan (excludes current incident)           │    │
│  │    /search-logs       → OpenSearch hybrid search → DynamoDB fallback        │    │
│  │    /get-runbook       → DynamoDB runbooks table                             │    │
│  │    /check-deployments → deployment history (service-specific)               │    │
│  │                                                                             │    │
│  │  Lambda: outageshield-agent-invoker-dev                                     │    │
│  │    Invokes agent, cleans XML tags, strips Remediation Summary bleed         │    │
│  │    Stores result in DynamoDB: agent_investigation field                     │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Stack 06-08: Orchestration + Notifications + Remediation ───────────────┐    │
│  │                                                                             │    │
│  │  Step Functions: outageshield-workflow-dev                                  │    │
│  │    9 steps, retries + error handling, each step writes to DynamoDB          │    │
│  │                                                                             │    │
│  │  SNS: outageshield-alerts-dev (email, Slack, PagerDuty)                     │    │
│  │  Jira Cloud API: auto-create tickets with full incident context             │    │
│  │  AWS Systems Manager: execute rollback / scale / config changes             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─── Stack 09-12: Dashboard + Auth + WebSocket + CloudFront ─────────────────┐    │
│  │                                                                             │    │
│  │  API Gateway REST: 601lnlm7r5.execute-api.us-east-1.amazonaws.com/dev      │    │
│  │    GET /incidents        → active incidents with full AI analysis           │    │
│  │    GET /risk             → service risk scores                              │    │
│  │    GET /postmortems      → AI postmortem reports                            │    │
│  │    POST /approve/{id}    → human approval for remediation                   │    │
│  │                                                                             │    │
│  │  API Gateway WebSocket: 2ciglpkye6.execute-api.us-east-1.amazonaws.com/dev │    │
│  │    Real-time incident updates via DynamoDB Streams                          │    │
│  │                                                                             │    │
│  │  Cognito User Pool: outageshield-users-dev                                  │    │
│  │  S3 Bucket: outageshield-ui-dev                                             │    │
│  │  CloudFront: d2k1km1tzlio49.cloudfront.net                                  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step Functions Workflow Detail

```
                    ┌─────────────────────────────────────────────────────┐
  Signal arrives    │  Step 1: Correlate  (120s timeout, 2 retries)       │
  ──────────────▶   │  • Creates incident record in DynamoDB              │
                    │  • Gathers deployment history + config changes       │
                    │  • Sets workflow_step = 'correlating'               │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 2: Score  (60s timeout, 5 retries)            │
                    │  Bedrock: severity 1-5, business impact 1-10        │
                    │  • affected_users, revenue_at_risk (specific $)     │
                    │  • sla_status, scoring_reasoning                    │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 3: Root Cause Analysis  (120s, 5 retries)     │
                    │  Bedrock: 3 ranked causes with confidence %         │
                    │  • root_causes_raw (JSON array)                     │
                    │  • root_cause (plain text, top cause)               │
                    │  • confidence score                                 │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 3b: Agent Investigation  (120s, 2 retries)    │
                    │  Bedrock Agent autonomously:                        │
                    │  • Searches past incidents (excludes current)       │
                    │  • Queries OpenSearch for alarm patterns            │
                    │  • Looks up runbook for alarm type                  │
                    │  • Checks deployment/config change history          │
                    │  Stores: agent_investigation (cleaned, 3000 chars)  │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 4: Remediation  (120s, 5 retries)             │
                    │  Bedrock: evidence-based recommendations            │
                    │  • Source attribution (AGENT:* or RCA)             │
                    │  • ensure_all_sources() — smart injection           │
                    │  • Negative evidence detection (no false positives) │
                    │  • remediation_summary (factual, no placeholders)   │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 5: Approval Gate                              │
                    │  If auto_remediation_enabled:                       │
                    │    waitForTaskToken → human approves/rejects        │
                    │  Else: skip to Step 6                               │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 6: Execute  (300s, 2 retries)                 │
                    │  AWS Systems Manager: run remediation document      │
                    │  • Rollback deployment                              │
                    │  • Scale resources                                  │
                    │  • Apply configuration change                       │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 7: Jira Ticket  (60s, 3 retries)              │
                    │  • Creates ticket with root cause + severity        │
                    │  • Includes dashboard link + recommendations        │
                    │  • Stores ticket_id, ticket_url in DynamoDB         │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 8: SNS Notification  (30s, 3 retries)         │
                    │  • Escalation alert to sre-team                     │
                    │  • Includes incident summary + ticket link          │
                    │  • Stores notification record in DynamoDB           │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                    ┌──────────────────────────▼──────────────────────────┐
                    │  Step 9: Postmortem  (120s, 5 retries)              │
                    │  Bedrock: uses ALL previous step outputs            │
                    │  • summary, root_cause (matches Step 3)             │
                    │  • prevention steps (specific to this root cause)   │
                    │  • impact (uses Step 2 revenue + users)             │
                    │  • Stores in outageshield-postmortems-dev           │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                                    workflow_step = 'postmortem'
                                    status = 'Investigating'
```

---

## CloudFormation Stacks

**13 stacks, fully serverless:**

| # | Stack | Services |
|---|-------|----------|
| 01 | Ingestion | EventBridge, Lambda |
| 02 | Storage | DynamoDB (4 tables), OpenSearch Serverless |
| 03 | Detection | Lambda (threshold evaluation, service name extraction) |
| 04 | Correlation | Lambda (incident context builder) |
| 05 | Reasoning | Bedrock Claude 3 Haiku, Lambda ×4 |
| 06 | Orchestration | Step Functions (9-step workflow) |
| 07 | Notifications | SNS, Lambda, Jira Cloud API |
| 08 | Remediation | Lambda, AWS Systems Manager |
| 09 | Dashboard | API Gateway REST, Lambda |
| 10 | Auth | Amazon Cognito |
| 11 | WebSocket | API Gateway WebSocket, DynamoDB Streams |
| 12 | CloudFront | S3 + CloudFront (React SPA) |
| 13 | Bedrock Agent | Bedrock Agent, Agent Actions Lambda, Agent Invoker Lambda |

---

The agent autonomously investigates each incident using 4 tools:

| Tool | Data Source | What It Does |
|------|-------------|-------------|
| `searchIncidentHistory` | DynamoDB | Find past incidents on same service (excludes current) |
| `searchLogs` | OpenSearch Serverless | Search alarm patterns and error messages |
| `getRunbook` | DynamoDB | Look up remediation procedures |
| `checkDeployments` | Deployment history | Find recent config/deployment changes |

Results feed directly into the Remediation Lambda as evidence for source-attributed recommendations.

---

## Anti-Hallucination Design

The Remediation Lambda enforces strict evidence-based rules:

- Every recommendation must cite its source: `RCA`, `AGENT:runbook`, `AGENT:past_incidents`, `AGENT:deployment_correlation`, `AGENT:log_patterns`, or `agent_advice`
- Sources are only used when the agent **actually found data** — negative signals ("No deployments found", "No past incidents") suppress injection
- `ensure_all_sources()` deterministically injects missing sources only when positive evidence exists
- Confidence 90%+ requires runbook match or 3+ past incidents; below 70% for inference only
- Falls back to `manual_intervention` with `agent_advice` when data is lacking

---

## AI Scoring — Business Impact Estimation

The Scoring Lambda reasons step-by-step about each incident's business impact against a $500M/year ($57K/hour) baseline:

| Impact Level | Score | Revenue at Risk | SLA Status |
|---|---|---|---|
| Critical | 8-10 | $30K-$50K/hour | Breached |
| High | 6-7 | $3K-$10K/hour | At Risk |
| Medium | 4-5 | $500-$3K/hour | Warning |
| Low | 2-3 | $0-$500/hour | OK |
| Internal | 1-2 | $0 | OK |

**Outputs per incident:** `severity_score`, `business_impact_score`, `affected_users`, `revenue_at_risk` (specific dollar amount), `sla_status`, `scoring_reasoning`

---

## Dashboard UI

React 18 + TypeScript + Vite + Tailwind CSS

- **Dashboard** — active incidents, service risk heatmap, business impact
- **Incident Detail** — root causes with confidence bars + evidence, remediation recommendations with source badges, autonomous agent investigation (4 sections), Jira ticket, SNS notification
- **Postmortems** — AI-generated reports with summary, root cause, impact, prevention steps
- **Real-time** — WebSocket push from DynamoDB Streams

---

## Data Model

### Incident Record (DynamoDB: `outageshield-incidents-dev`)

```json
{
  "incident_id": "INC-CC935145",
  "service": "checkout-service",
  "title": "Outage signal on checkout-service",
  "status": "Investigating",
  "workflow_step": "postmortem",
  "created_at": "2026-05-23T19:16:27Z",

  "severity_score": 4,
  "business_impact_score": 8,
  "affected_users": 800000,
  "revenue_at_risk": "$22,800/hour (40% of hourly revenue)",
  "sla_status": "At Risk",
  "scoring_reasoning": "checkout-service handles payment processing...",

  "root_cause": "Increased traffic or request volume leading to resource exhaustion",
  "confidence": 80,
  "root_causes_raw": "[{\"description\":\"...\",\"confidence\":80,\"evidence\":\"...\"}]",

  "agent_investigation": "[Source: Incident History DB]\n...\n[Source: OpenSearch Logs]\n...",

  "recommendations_raw": "[{\"category\":\"rollback\",\"source\":\"AGENT:deployment_correlation\",...}]",
  "remediation_summary": "OpenSearch logs showing 5xx, timeout; recent deployment/config changes identified -- primary action: Rollback...",

  "ticket_id": "TGSHLD-1234",
  "ticket_status": "Open",
  "notifications": "{\"type\":\"escalation\",\"recipient\":\"sre-team@...\"}",
  "postmortem_generated": true
}
```

### Postmortem Record (DynamoDB: `outageshield-postmortems-dev`)

```json
{
  "postmortem_id": "PM-3a22bc74",
  "incident_id": "INC-CC935145",
  "service": "checkout-service",
  "root_cause": "Increased traffic or request volume leading to resource exhaustion",
  "summary": "The checkout-service experienced a high rate of 5xx errors...",
  "duration": "2-3 hours",
  "prevention": "[\"Implement dynamic scaling\",\"Load shedding mechanisms\",\"Capacity planning\"]",
  "impact_summary": {"revenue_at_risk": "$22,800/hour", "affected_users": "800000"},
  "scoring_reasoning": "checkout-service is a critical component...",
  "created_at": "2026-05-23T19:16:27Z"
}
```

### Runbook Record (DynamoDB: `outageshield-runbooks-dev`)

```json
{
  "runbook_id": "HighLatency",
  "title": "High Latency Recovery",
  "steps": ["Check CloudWatch metrics", "Review recent deployments", "Check connection pool", "Scale up if needed"],
  "category": "manual_intervention",
  "estimated_ttr": "15 minutes",
  "severity_threshold": 3
}
```

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
python scripts/lambdas/update-rca-lambda-v2.py
python scripts/lambdas/update-remediation-lambda2.py
python scripts/lambdas/update-postmortem-lambda.py
python scripts/lambdas/update-detection-opensearch.py
python scripts/lambdas/fix-agent-actions.py
python scripts/lambdas/update-agent-invoker.py
python scripts/lambdas/update-scoring-lambda.py
```

### Run the UI Locally
```bash
cd UI
npm install
npm run dev
```

### Deploy the UI
```bash
cd UI
npm run build
aws s3 sync dist s3://outageshield-ui-dev --delete --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/clear-and-push.py` | Delete all data (keep runbooks) + push 100 fresh incidents |
| `scripts/test-one.py` | Trigger one incident and trace the full pipeline |
| `scripts/test-complex.py` | Trigger a complex incident (different service/alarm type) |
| `scripts/rebuild-layer.py` | Rebuild the opensearch-py Lambda Layer |
| `scripts/lambdas/update-remediation-lambda2.py` | Deploy Remediation Lambda (anti-hallucination + smart source injection) |
| `scripts/lambdas/update-rca-lambda-v2.py` | Deploy RCA Lambda (bulletproof parsing) |
| `scripts/lambdas/update-postmortem-lambda.py` | Deploy Postmortem Lambda (uses all previous steps) |
| `scripts/lambdas/update-detection-opensearch.py` | Deploy Detection Lambda (correct service name extraction) |
| `scripts/lambdas/fix-agent-actions.py` | Deploy Agent Actions Lambda (OpenSearch hybrid search) |
| `scripts/lambdas/update-agent-invoker.py` | Deploy Agent Invoker Lambda (XML tag cleaning) |
| `scripts/lambdas/update-scoring-lambda.py` | Deploy Scoring Lambda (specific revenue amounts) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Reasoning | Amazon Bedrock (Claude 3 Haiku) |
| Autonomous Agent | Amazon Bedrock Agents |
| Orchestration | AWS Step Functions |
| Compute | AWS Lambda (Python 3.12) + opensearch-py Layer |
| Storage | DynamoDB (4 tables), OpenSearch Serverless |
| Ingestion | Amazon EventBridge |
| Notifications | Amazon SNS, Jira Cloud API |
| Remediation | AWS Systems Manager |
| Auth | Amazon Cognito |
| Real-time | API Gateway WebSocket + DynamoDB Streams |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Hosting | S3 + CloudFront |
| IaC | AWS CloudFormation (13 stacks) |
