# OutageShield AI — Lambda Deployment Scripts

This folder contains Python scripts to deploy and update Lambda function code for the OutageShield AI platform.

---

## Quick Reference

| Script | Lambda Function | Purpose |
|--------|-----------------|---------|
| `update-detection-opensearch.py` | `outageshield-detection-dev` | Detect anomalies, create incidents, index to OpenSearch |
| `update-correlation-lambda.py` | `outageshield-correlation-dev` | Correlate alerts with deployments, config changes, history |
| `update-scoring-lambda.py` | `outageshield-scoring-dev` | Calculate severity, impact, downstream users, AWS costs |
| `update-rca-lambda-v2.py` | `outageshield-rootcause-dev` | AI root cause analysis with 5 categories |
| `update-agent-invoker.py` | `outageshield-agent-invoker-dev` | Orchestrate Bedrock Agent investigation |
| `update-agent-actions-all-tools.py` | `outageshield-agent-actions-dev` | Execute 6 agent investigation tools |
| `update-remediation-lambda3.py` | `outageshield-remediation-recommend-dev` | AI-powered evidence-based recommendations |
| `create-summary-lambda.py` | `outageshield-remediation-summary-dev` | AI summary with best action and quick commands |
| `update-postmortem-lambda.py` | `outageshield-postmortem-dev` | Generate AI postmortem with prevention steps |
| `update-approval-with-sn-url.py` | `outageshield-approval-dev` | Human approval gate with ServiceNow URL |
| `update-dashboard-api-with-approval.py` | `outageshield-dashboard-api-dev` | Dashboard REST API with approval endpoints |

---

## Workflow Order

The Lambdas execute in this order during incident processing:

```
1. Detection          → outageshield-detection-dev
2. Correlation        → outageshield-correlation-dev
3. Scoring            → outageshield-scoring-dev
4. Root Cause         → outageshield-rootcause-dev
5. Agent Investigation → outageshield-agent-invoker-dev
                         └── outageshield-agent-actions-dev (6 tools)
6. Remediation        → outageshield-remediation-recommend-dev
7. Summary            → outageshield-remediation-summary-dev
8. Approval           → outageshield-approval-dev (waitForTaskToken)
9. Execution          → outageshield-remediation-executor-dev
10. Ticket            → outageshield-ticket-integrator-dev
11. Notification      → outageshield-notification-dev
12. Postmortem        → outageshield-postmortem-dev
```

---

## Lambda Details

### 1. Detection Lambda (`update-detection-opensearch.py`)

**Function**: `outageshield-detection-dev`

Processes CloudWatch alarms from EventBridge and creates incident records.

**Features**:
- Parses CloudWatch alarm events
- Creates incident record in DynamoDB
- Indexes event in OpenSearch Serverless
- Triggers Step Functions workflow

**Usage**:
```bash
python scripts/lambdas/update-detection-opensearch.py
```

---

### 2. Correlation Lambda (`update-correlation-lambda.py`)

**Function**: `outageshield-correlation-dev`

Gathers context from multiple sources to build incident context.

**Data Sources**:
- Related alarms (same service, time window)
- Recent deployments from DynamoDB
- Config changes from DynamoDB
- Past incidents for the service
- Related logs from OpenSearch

**Usage**:
```bash
python scripts/lambdas/update-correlation-lambda.py
```

---

### 3. Scoring Lambda (`update-scoring-lambda.py`)

**Function**: `outageshield-scoring-dev`

Calculates business impact scores with AWS cost-based revenue estimation and downstream user impact.

**Output**:
- `severity_score`: 1-5 (Info, Low, Medium, Warning, Critical)
- `business_impact_score`: 1-10
- `affected_users`: **Downstream impact** - users affected if monitored service fails
- `revenue_at_risk`: AWS cost per hour (e.g., `$0.01/hour`)
- `sla_status`: OK, Warning, At Risk, Breached
- `scoring_reasoning`: Explanation of the scoring

**Key Features**:
- **Extracts core service name** from monitoring alarms (e.g., `legalmind-renewal` from `legalmind-dev-alarm-renewal-monitor-failed`)
- **Downstream impact estimation** - shows users affected by the monitored service, not the monitor itself
- **AWS cost-based revenue** - queries CloudWatch for actual Lambda invocations and calculates cost
- **Service classification** by business function:
  - `critical_revenue`: Payment, checkout, billing → 50,000 users
  - `business_critical`: Renewal, subscription, compliance → 25,000 users
  - `user_facing`: Auth, login, session → 15,000 users
  - `infrastructure`: API gateway, proxy → 10,000 users
  - `data`: Database, cache → 5,000 users
  - `messaging`: Queue, notifications → 2,000 users

**Usage**:
```bash
python scripts/lambdas/update-scoring-lambda.py
```

---

### 4. Root Cause Lambda (`update-rca-lambda-v2.py`)

**Function**: `outageshield-rootcause-dev`

AI-powered root cause analysis with category classification.

**RCA Categories**:
| Category | Description | Color |
|----------|-------------|-------|
| `capacity` | Resource exhaustion | 🔴 Red |
| `performance` | Latency/throughput issues | 🟠 Orange |
| `configuration` | Misconfiguration | 🟡 Amber |
| `deployment` | Bad deploy/version mismatch | 🔵 Blue |
| `dependency` | External service failures | 🟣 Purple |

**Output**:
- Up to 3 ranked root causes
- Confidence score (0-100%)
- Category classification
- Supporting evidence

**Usage**:
```bash
python scripts/lambdas/update-rca-lambda-v2.py
```

---

### 5. Agent Invoker (`update-agent-invoker.py`)

**Function**: `outageshield-agent-invoker-dev`

Orchestrates the Bedrock Agent for deep incident investigation.

**Features**:
- Invokes Bedrock Agent with incident context
- Handles agent session management
- Collects investigation results from all tools

**Usage**:
```bash
python scripts/lambdas/update-agent-invoker.py
```

---

### 6. Agent Actions (`update-agent-actions-all-tools.py`)

**Function**: `outageshield-agent-actions-dev`

Executes the 6 investigation tools called by the Bedrock Agent.

**Tools**:
| Tool | Description | Data Source |
|------|-------------|-------------|
| `searchIncidentHistory` | Find similar past incidents | DynamoDB |
| `searchLogs` | Query error patterns | OpenSearch Serverless |
| `getRunbook` | Look up remediation runbook | DynamoDB |
| `checkDeployments` | Check recent deployments | DynamoDB |
| `searchTraces` | Query latency/error traces | AWS X-Ray |
| `checkConfigDrift` | Check compliance issues | AWS Config |

**Usage**:
```bash
python scripts/lambdas/update-agent-actions-all-tools.py
```

---

### 7. Remediation Lambda (`update-remediation-lambda3.py`)

**Function**: `outageshield-remediation-recommend-dev`

AI-powered remediation recommendations that **cite specific investigation sources**.

**Investigation Sources Used**:
| Source | Data | Example Citation |
|--------|------|------------------|
| OpenSearch Logs | Log entries, alarm occurrences | "Found 10 log entries with 5 Threshold Crossed events" |
| X-Ray Traces | Requests, errors, faults, latency | "Captured 100 requests with 5 errors, P99: 250ms" |
| Runbook DB | Available runbooks, steps | "Runbook available with 5 documented steps" |
| Deployment History | Recent deployments, config changes | "Found 2 deployments in the last 24 hours" |
| AWS Config | Compliance issues, drift | "Found 1 non-compliant resource" |
| Incident History | Past similar incidents | "Found 3 past incidents for this service" |

**Recommendation Categories**:
| Category | Description | Example |
|----------|-------------|---------|
| `immediate_mitigation` | Stop the bleeding NOW | Increase alarm threshold |
| `root_cause_remediation` | Fix the underlying issue | Analyze CloudWatch metrics |
| `configuration` | Config/parameter changes | Update connection pool |
| `monitoring` | Improve observability | Enable X-Ray tracing |
| `prevention` | Prevent recurrence | Automate runbook |

**Key Features**:
- **Source citations**: Each recommendation includes `[Source: X]` in reasoning
- **Evidence-based**: Only recommends based on actual data found
- **Anti-hallucination**: Won't recommend rollback if no deployments found
- **Recurring detection**: Identifies patterns from alarm occurrences
- **AWS CLI commands**: Includes specific commands for each action

**Output per Recommendation**:
```json
{
  "category": "immediate_mitigation",
  "title": "Increase alarm threshold",
  "description": "What to do and why",
  "reasoning": "[Source: OpenSearch Logs] Found 5 Threshold Crossed events...",
  "source": "OpenSearch Logs",
  "aws_command": "aws cloudwatch put-metric-alarm ...",
  "estimated_ttr_minutes": 15,
  "risk": "low",
  "confidence": 80,
  "verification": "How to verify the fix"
}
```

**Example Dashboard Output**:
```
#1 [immediate_mitigation] RECOMMENDED 80% low risk 15m TTR
   Increase the alarm threshold temporarily
   Source: OpenSearch Logs
   Reasoning: Found 10 log entries with 5 "Threshold Crossed" events in 24 hours

#2 [root_cause_remediation] 75% medium risk 60m TTR
   Analyze CloudWatch metrics for traffic spikes
   Source: X-Ray Traces
   Reasoning: X-Ray shows 0 requests traced - enable tracing for visibility

#3 [prevention] 90% low risk 120m TTR
   Automate the runbook for this alarm
   Reasoning: Manual runbook exists, automation reduces TTR
```

**Usage**:
```bash
python scripts/lambdas/update-remediation-lambda3.py
```

---

### 8. Summary Lambda (`create-summary-lambda.py`)

**Function**: `outageshield-remediation-summary-dev`

Generates AI-powered summary with actionable quick commands.

**Output**:
- `ai_summary`: 3-4 sentence technical summary
- `recommended_action`: Best recommendation with confidence
- `quick_actions`: 8 AWS CLI commands ready to run
- `investigation_summary`: Key metrics and findings

**Special Handling**:
- EventBridge failures → Lambda permission/throttling commands
- Recurring alarms → Permanent fix recommendations
- Renewal services → Payment gateway checks

**Usage**:
```bash
python scripts/lambdas/create-summary-lambda.py
```

---

### 9. Postmortem Lambda (`update-postmortem-lambda.py`)

**Function**: `outageshield-postmortem-dev`

Generates comprehensive AI postmortem reports.

**Postmortem Sections**:
- Executive Summary
- Timeline of events
- Impact Analysis (users, revenue, duration)
- Root Cause (with category)
- Investigation Findings
- Remediation Actions Taken
- **AI Prevention Recommendations** (5 steps based on RCA category)
- Lessons Learned

**Prevention by Category**:
| Category | Prevention Focus |
|----------|------------------|
| capacity | Auto-scaling, capacity planning |
| performance | Query optimization, caching |
| configuration | Config validation, IaC |
| deployment | Canary deploys, rollback automation |
| dependency | Circuit breakers, fallbacks |

**Usage**:
```bash
python scripts/lambdas/update-postmortem-lambda.py
```

---

### 10. Approval Lambda (`update-approval-with-sn-url.py`)

**Function**: `outageshield-approval-dev`

Human approval gate using Step Functions `waitForTaskToken`.

**Features**:
- Stores task token in DynamoDB
- Updates incident to "Awaiting Approval"
- Sends SNS notification with approval link
- Includes ServiceNow change request URL

**Usage**:
```bash
python scripts/lambdas/update-approval-with-sn-url.py
```

---

### 11. Dashboard API (`update-dashboard-api-with-approval.py`)

**Function**: `outageshield-dashboard-api-dev`

REST API for the React dashboard.

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/incidents` | List all incidents |
| GET | `/incidents/{id}` | Get incident details |
| POST | `/approve/{id}` | Approve/reject remediation |
| GET | `/postmortems` | List postmortems |
| GET | `/stats` | Dashboard statistics |

**Usage**:
```bash
python scripts/lambdas/update-dashboard-api-with-approval.py
```

---

## Utility Scripts

### Rerun Lambdas for Specific Incidents

```bash
# Edit INCIDENTS list in the script first
python scripts/rerun-lambdas.py
```

This reruns scoring, remediation, and summary Lambdas for specified incidents to regenerate their data with updated logic.

---

## Deployment Order

When deploying all Lambdas, follow this order to ensure dependencies are met:

```bash
# 1. Core workflow Lambdas
python scripts/lambdas/update-detection-opensearch.py
python scripts/lambdas/update-correlation-lambda.py
python scripts/lambdas/update-scoring-lambda.py
python scripts/lambdas/update-rca-lambda-v2.py

# 2. Agent Lambdas
python scripts/lambdas/update-agent-invoker.py
python scripts/lambdas/update-agent-actions-all-tools.py

# 3. Remediation Lambdas
python scripts/lambdas/update-remediation-lambda2.py
python scripts/lambdas/create-summary-lambda.py

# 4. Post-workflow Lambdas
python scripts/lambdas/update-postmortem-lambda.py
python scripts/lambdas/update-approval-with-sn-url.py
python scripts/lambdas/update-dashboard-api-with-approval.py
```

---

## Environment Variables

All Lambdas use these common environment variables (set in CloudFormation):

| Variable | Description |
|----------|-------------|
| `INCIDENTS_TABLE` | DynamoDB incidents table |
| `EVENTS_TABLE` | DynamoDB events table |
| `RUNBOOKS_TABLE` | DynamoDB runbooks table |
| `DEPLOYMENTS_TABLE` | DynamoDB deployments table |
| `OPENSEARCH_ENDPOINT` | OpenSearch Serverless endpoint |
| `MODEL_ID` | Bedrock model ID |
| `AGENT_ID` | Bedrock Agent ID |
| `AGENT_ALIAS_ID` | Bedrock Agent alias |

---

## Troubleshooting

### Lambda Timeout
Increase timeout in CloudFormation stack or use:
```bash
aws lambda update-function-configuration \
  --function-name outageshield-<name>-dev \
  --timeout 120
```

### Bedrock Throttling
The Lambdas have retry logic with exponential backoff. If still failing:
- Check Bedrock service quotas
- Reduce concurrent executions

### View Lambda Logs
```bash
aws logs tail /aws/lambda/outageshield-<name>-dev --follow
```

### Test Lambda Manually
```bash
aws lambda invoke \
  --function-name outageshield-scoring-dev \
  --payload '{"signal": {"signal_id": "INC-TEST", "service": "test-service"}}' \
  response.json
cat response.json
```
