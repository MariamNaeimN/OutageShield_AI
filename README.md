# OutageShield AI

AI-powered incident detection, root-cause analysis, autonomous investigation, and automated remediation for enterprise cloud operations. Built on AWS with Amazon Bedrock (Claude 3 Haiku) as the reasoning engine and a Bedrock Agent for autonomous investigation.

**Live Dashboard:** https://d2k1km1tzlio49.cloudfront.net

---

## Key Features

| Feature | Description |
|---------|-------------|
| **6 Investigation Tools** | Bedrock Agent autonomously queries 6 data sources |
| **6 Remediation Sources** | Rule-based recommendations from all investigation data |
| **Anti-Hallucination** | Pure rule-based output formatting — no AI interpretation |
| **Jira + PagerDuty** | Dual ticketing system support |
| **AWS X-Ray** | Trace analysis for latency and error patterns |
| **AWS Config** | Compliance checking and drift detection |
| **Real-time Dashboard** | WebSocket-powered live updates |

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
│  │  ORCHESTRATION LAYER — Step Functions Workflow (10 steps)                    │   │
│  │                                                                              │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────────┐  │   │
│  │  │ Step 1   │   │ Step 2   │   │ Step 3   │   │ Step 4                   │  │   │
│  │  │Correlate │──▶│  Score   │──▶│   RCA    │──▶│  Bedrock Agent           │  │   │
│  │  │          │   │          │   │          │   │  6-Tool Investigation    │  │   │
│  │  │• Context │   │• Severity│   │• 3 causes│   │  • Past incidents        │  │   │
│  │  │• History │   │• Revenue │   │• Confid. │   │  • OpenSearch logs       │  │   │
│  │  │• Deploys │   │• Users   │   │• Evidence│   │  • Runbooks              │  │   │
│  │  │          │   │• SLA     │   │          │   │  • Deployments           │  │   │
│  │  │          │   │          │   │          │   │  • X-Ray traces          │  │   │
│  │  │          │   │          │   │          │   │  • Config drift          │  │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────────────────────┘  │   │
│  │                                                            │                  │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┴───────────────┐  │   │
│  │  │ Step 10  │   │ Step 9   │   │ Step 8   │   │ Step 5                   │  │   │
│  │  │Postmortem│◀──│  Notify  │◀──│  Ticket  │◀──│  Remediation (6 sources) │  │   │
│  │  │          │   │          │   │          │   │  • Rule-based logic      │  │   │
│  │  │• Summary │   │• SNS     │   │• Jira    │   │  • Source attribution    │  │   │
│  │  │• Root    │   │• Email   │   │• Service │   │  • Anti-hallucination    │  │   │
│  │  │  cause   │   │          │   │   Now    │   │  • No AI interpretation  │  │   │
│  │  │• Prevent │   │          │   │          │   └──────────────────────────┘  │   │
│  │  └──────────┘   └──────────┘   └──────────┘            │                   │   │
│  │                                                          ▼                   │   │
│  │                                              ┌──────────────────────────┐    │   │
│  │                                              │ Step 6: Approval Gate    │    │   │
│  │                                              │ (human-in-the-loop)      │    │   │
│  │                                              │         │                │    │   │
│  │                                              │         ▼                │    │   │
│  │                                              │ Step 7: Execute (SSM)    │    │   │
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
│  │  ├── outageshield-runbooks-dev                                               │   │
│  │  └── outageshield-deployments-dev  ← CI/CD + CloudTrail integration          │   │
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

## Bedrock Agent — 6 Investigation Tools

The agent autonomously investigates each incident using **6 tools**:

| # | Tool | Data Source | What It Does |
|---|------|-------------|-------------|
| 1 | `searchIncidentHistory` | DynamoDB | Find past incidents on same service |
| 2 | `searchLogs` | OpenSearch Serverless | Search alarm patterns and error messages |
| 3 | `getRunbook` | DynamoDB | Look up remediation procedures |
| 4 | `checkDeployments` | DynamoDB + CloudTrail | Find recent deployments and config changes |
| 5 | `searchTraces` | **AWS X-Ray** | Query traces for latency, errors, dependencies |
| 6 | `checkConfigDrift` | **AWS Config** | Check compliance issues and configuration drift |

### Anti-Hallucination Design

```
Bedrock Agent (enableTrace=True)
        │
        ▼
Extract RAW tool results from trace (actionGroupInvocationOutput)
        │
        ▼
Format output with PURE RULE-BASED logic
        │
        ▼
NO LLM text interpretation = NO hallucination
```

---

## Remediation — 6 Sources

The Remediation Lambda uses **pure rule-based logic** (no AI) to generate recommendations:

| # | Source | Description | Data Origin |
|---|--------|-------------|-------------|
| 1 | `AGENT:deployment_correlation` | Recent deployments/config changes | DynamoDB + CloudTrail |
| 2 | `AGENT:log_patterns` | Log analysis findings | OpenSearch Serverless |
| 3 | `AGENT:runbook` | Runbook-based procedures | DynamoDB runbooks table |
| 4 | `AGENT:past_incidents` | Similar past incidents | DynamoDB incidents table |
| 5 | `AGENT:xray_traces` | X-Ray trace analysis | AWS X-Ray |
| 6 | `AGENT:config_drift` | Compliance/drift issues | AWS Config |

### Recommendation Categories

| Category | Description | Risk |
|----------|-------------|------|
| `rollback` | Revert to previous version | Medium |
| `scaling` | Scale horizontally or vertically | Low |
| `configuration_change` | Update config parameters | Medium |
| `manual_intervention` | Requires human action | Low |

---

## Ticketing Integration

OutageShield supports **both Jira and PagerDuty**:

| System | Features |
|--------|----------|
| **Jira Cloud** | Full API integration, rich formatting, priority mapping |
| **PagerDuty** | Events API v2, severity mapping, deduplication, mobile alerts |

### Configuration

Set `TICKET_SYSTEM` environment variable:

| Value | Behavior |
|-------|----------|
| `jira` | Jira only |
| `pagerduty` | PagerDuty only |
| `both` | Create tickets in both systems (default) |

### PagerDuty Setup

1. Sign up at https://www.pagerduty.com/sign-up-free/
2. Create a Service with **Events API v2** integration
3. Copy the **Integration Key** (routing key)

```bash
# Update secret with your routing key
aws secretsmanager update-secret \
  --secret-id outageshield/pagerduty-credentials \
  --secret-string '{
    "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY",
    "api_key": ""
  }'
```

### PagerDuty Features

- **Events API v2** - Industry standard for incident creation
- **Severity Mapping** - SEV-5/4 → critical, SEV-3 → error, SEV-2 → warning, SEV-1 → info
- **Deduplication** - Uses incident_id as dedup_key to prevent duplicates
- **Dashboard Link** - Included in custom_details for quick access
- **Real-time Alerts** - Immediate notification via PagerDuty mobile app

---

## CloudFormation Stacks

**15 stacks, fully serverless:**

| # | Stack | Services |
|---|-------|----------|
| 01 | Ingestion | EventBridge, Lambda |
| 02 | Storage | DynamoDB (5 tables), OpenSearch Serverless |
| 03 | Detection | Lambda (threshold evaluation) |
| 04 | Correlation | Lambda (incident context builder) |
| 05 | Reasoning | Bedrock Claude 3 Haiku, Lambda ×4 |
| 06 | Orchestration | Step Functions (10-step workflow) |
| 07 | Notifications | SNS, Lambda, Jira + PagerDuty |
| 08 | Remediation | Lambda, AWS Systems Manager |
| 09 | Dashboard | API Gateway REST, Lambda |
| 10 | Auth | Amazon Cognito |
| 11 | WebSocket | API Gateway WebSocket, DynamoDB Streams |
| 12 | CloudFront | S3 + CloudFront (React SPA) |
| 13 | Bedrock Agent | Bedrock Agent (6 tools), Agent Invoker Lambda |
| 14 | CloudTrail | Deployment tracking from CloudTrail events |
| 15 | X-Ray + Config | X-Ray tracing, AWS Config drift detection |

---

## SNS Notifications

Each incident generates a detailed SNS notification:

```
OutageShield AI - Incident Alert
==================================================

Service:         payment-gateway
Severity:        SEV-4
Incident ID:     INC-ABC12345
Alarm:           High5xxRate-payment-gateway

Root Cause:      Database connection pool exhaustion
Confidence:      85%
Revenue at Risk: $15,000/hour
Affected Users:  12,500

Recommendations: 6 actions available
Sources:         6 (deployment, logs, runbook, history, X-Ray, Config)

Jira Ticket:     OPS-1234
Ticket URL:      https://company.atlassian.net/browse/OPS-1234

Dashboard:       https://d2k1km1tzlio49.cloudfront.net/incidents/INC-ABC12345

==================================================
Action Required: Review incident and approve remediation.
```

---

## Dashboard UI

React 18 + TypeScript + Vite + Tailwind CSS

### Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Active incidents, service risk heatmap, business impact |
| **Incident Detail** | Full investigation with 6 sources, recommendations, tickets |
| **Postmortems** | AI-generated reports with prevention steps |

### Incident Detail Sections

| Section | Content |
|---------|---------|
| **Root Cause Analysis** | AI-identified causes with confidence %, evidence |
| **Recommended Actions** | 6 source-attributed recommendations with risk level |
| **Technical Investigation** | Bedrock Agent findings from all 6 tools |
| **X-Ray Traces** | Error traces, slow traces, service stats, insights |
| **AWS Config** | Non-compliant resources, recent changes, violations |
| **SNS Notification** | Recipient, subject, full message, sent timestamp |
| **Ticket** | Jira + PagerDuty links and status |
| **Business Impact** | Revenue at risk, affected users, SLA status |

---

## Quick Start

### Deploy Stacks

```bash
cd stacks
chmod +x deploy.sh
./deploy.sh dev us-east-1
```

### Deploy Lambda Code

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

### Refresh All Incidents

```bash
python scripts/refresh-all-investigations.py
```

---

## Project Structure

```
OutageShield AI/
├── stacks/                     # CloudFormation templates (15 stacks)
│   ├── 01-ingestion-stack.yaml
│   ├── 02-storage-stack.yaml
│   ├── ...
│   ├── 13-bedrock-agent-stack.yaml
│   ├── 14-cloudtrail-deployments-stack.yaml
│   ├── 15-xray-config-stack.yaml
│   └── stepfunctions/          # Step Functions workflow
├── scripts/
│   ├── lambdas/                # Lambda deployment scripts
│   │   ├── add-xray-config-tools.py
│   │   ├── update-agent-invoker.py
│   │   ├── update-remediation-lambda2.py
│   │   └── add-pagerduty-integration.py
│   ├── refresh-all-investigations.py
│   └── rerun-single-incident.py
├── UI/                         # React dashboard
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── services/
│   └── package.json
├── dashboard-api-code/         # API Lambda code
└── docs/                       # Documentation
    ├── data-ingestion-guide.md
    └── continuous-learning.md
```

---

## AWS Services Used

| Service | Purpose |
|---------|---------|
| Amazon Bedrock | Claude 3 Haiku for AI reasoning |
| Bedrock Agents | Autonomous investigation with 6 tools |
| AWS Lambda | Serverless compute (15+ functions) |
| Amazon DynamoDB | Incident, event, runbook, deployment storage |
| OpenSearch Serverless | Log search and correlation |
| AWS Step Functions | 10-step incident workflow |
| Amazon EventBridge | Event routing and triggers |
| Amazon SNS | Alert notifications |
| AWS Systems Manager | Remediation execution |
| Amazon API Gateway | REST + WebSocket APIs |
| Amazon Cognito | User authentication |
| Amazon S3 + CloudFront | Dashboard hosting |
| AWS X-Ray | Application tracing |
| AWS Config | Configuration compliance |
| AWS CloudTrail | Deployment tracking |

---

## Definition of Done ✅

| Requirement | Status |
|-------------|--------|
| Agent detects and correlates alerts, logs, telemetry, and changes | ✅ |
| Agent identifies likely root cause and recommends remediation | ✅ |
| User can view outage risk, business impact, and incident status | ✅ |
| System can create tickets (Jira + PagerDuty) | ✅ |
| System generates incident/postmortem summaries | ✅ |
| AWS X-Ray integration | ✅ |
| AWS Config integration | ✅ |
| Anti-hallucination design | ✅ |
| 6 investigation tools | ✅ |
| 6 remediation sources | ✅ |

---

## License

MIT License - See LICENSE file for details.
