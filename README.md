# OutageShield AI

**AI-Powered Incident Detection, Correlation, and Remediation Platform for Enterprise Cloud Operations**

[![AWS](https://img.shields.io/badge/AWS-Cloud-orange)](https://aws.amazon.com)
[![Bedrock](https://img.shields.io/badge/Amazon-Bedrock-blue)](https://aws.amazon.com/bedrock/)
[![React](https://img.shields.io/badge/React-18.3-61dafb)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-blue)](https://www.typescriptlang.org)
[![Last Updated](https://img.shields.io/badge/Updated-May%2029%2C%202026-green)]()

---

## Overview

OutageShield AI is an enterprise-grade incident management platform that leverages Amazon Bedrock and AWS services to automatically detect, investigate, and remediate cloud infrastructure incidents. The system ingests operational data from multiple AWS sources, correlates alerts with deployment and configuration changes, identifies root causes using AI, and recommends or triggers remediation actions.

### Key Features

- **🔍 Early Outage Detection** - Detects anomalies in CloudWatch metrics, logs, and X-Ray traces before full service degradation
- **🤖 AI-Powered Root Cause Analysis** - Amazon Bedrock agent autonomously investigates incidents using 6 specialized tools with categorized root causes
- **🏷️ RCA Categorization** - Automatic classification of root causes into 5 categories: capacity, performance, configuration, deployment, dependency
- **📊 Intelligent Correlation** - Links alerts with deployments, config changes, and historical incidents
- **💡 Source-Based Remediation** - Generates recommendations that cite specific investigation sources (OpenSearch, X-Ray, Runbook, Deployments, Config, Incident History)
- **📈 Downstream Impact Scoring** - Estimates affected users based on the monitored service's business function, not the monitor itself
- **💰 AWS Cost-Based Revenue** - Calculates revenue at risk using actual CloudWatch metrics and AWS pricing
- **📋 AI Summary Generation** - Produces actionable summaries with best remediation suggestion and quick action commands
- **🎫 Ticketing Integration** - Automatic Jira (TGSHLD project), PagerDuty, and ServiceNow ticket creation with clickable links in UI
- **📱 Real-time Dashboard** - React-based incident command center with WebSocket updates and color-coded RCA category badges
- **📝 Auto-generated Postmortems** - AI-generated incident summaries with timeline, impact analysis, and lessons learned
- **🛡️ AI Prevention Recommendations** - LLM-generated long-term prevention steps based on RCA category and investigation context
- **🚨 Escalation Alerts** - Automatic escalation for high-severity incidents (severity >= 4)
- **📧 SNS Email Notifications** - Email alerts to sre-team@shopsphere.com for alerts, approvals, and escalations
- **✅ Human Approval Gate** - Dashboard-based or ServiceNow approval workflow with waitForTaskToken pattern
- **🧠 Continuous Learning** - System learns from every resolved incident to improve detection, correlation, and root-cause accuracy over time

---

## RCA Categories

Root causes are automatically classified into 5 categories for better remediation targeting:

| Category | Description | Example Causes | Prevention Focus |
|----------|-------------|----------------|------------------|
| **capacity** | Resource exhaustion issues | CPU/memory limits, disk full, connection pool exhausted | Auto-scaling, capacity planning, resource monitoring |
| **performance** | Latency and throughput issues | Slow queries, high latency, timeout errors | Performance optimization, caching, query tuning |
| **configuration** | Misconfiguration issues | Wrong settings, invalid parameters, missing config | Config validation, IaC, change management |
| **deployment** | Deployment-related issues | Bad deploy, version mismatch, rollback needed | CI/CD improvements, canary deployments, rollback automation |
| **dependency** | External dependency failures | Third-party API down, database unavailable | Circuit breakers, fallbacks, dependency health checks |

The UI displays color-coded badges for each category:
- 🔴 **capacity** - Red badge
- 🟠 **performance** - Orange badge  
- 🟡 **configuration** - Amber badge
- 🔵 **deployment** - Sky blue badge
- 🟣 **dependency** - Purple badge

---

## AI-Powered Features

### Root Cause Analysis (RCA)
The RCA Lambda uses Amazon Bedrock (Claude 3 Haiku) to analyze incident context and determine:
- Primary root cause with confidence score (0-100%)
- Category classification (capacity/performance/configuration/deployment/dependency)
- Supporting evidence from logs, metrics, and traces

### Business Impact Scoring
The scoring Lambda calculates business impact with:
- **Downstream impact estimation** - Shows users affected by the monitored service, not the monitor itself
- **AWS cost-based revenue** - Queries CloudWatch for actual Lambda invocations and calculates cost per hour
- **Service classification** by business function (critical_revenue, business_critical, user_facing, infrastructure, data, messaging)
- Extracts core service name from monitoring alarms (e.g., `legalmind-renewal` from `legalmind-dev-alarm-renewal-monitor-failed`)

### Remediation Recommendations
The system generates **source-based recommendations** that cite specific investigation sources:

| Investigation Source | Data Used | Example Recommendation |
|---------------------|-----------|------------------------|
| **OpenSearch Logs** | Log entries, alarm occurrences | "OpenSearch shows 6 Threshold Crossed events - increase alarm threshold" |
| **X-Ray Traces** | Requests, errors, faults, latency | "X-Ray shows 0 requests - enable tracing" |
| **Runbook DB** | Available runbooks, steps | "Follow 5-step runbook for troubleshooting" |
| **Deployment History** | Recent deployments, config changes | "No deployments found - investigate non-deployment causes" |
| **AWS Config** | Compliance issues, drift | "Found 1 non-compliant resource - fix config" |
| **Incident History** | Past similar incidents | "3 past incidents found - implement permanent fix" |

**Anti-hallucination rules enforced**:
- Won't recommend rollback if no deployments found
- Won't claim "service healthy" if X-Ray shows 0 requests
- Each recommendation cites its source in the reasoning field

### AI Prevention Recommendations
Postmortems include LLM-generated long-term prevention steps based on:
- RCA category (capacity, performance, configuration, deployment, dependency)
- Service name and alarm type
- Investigation findings from all 6 agent tools
- Remediation actions taken

Example prevention recommendations by category:
- **Capacity**: "Implement proactive capacity planning with 30% headroom"
- **Performance**: "Add caching layer to reduce database load"
- **Configuration**: "Implement configuration validation in CI/CD pipeline"
- **Deployment**: "Enable canary deployments with automatic rollback"
- **Dependency**: "Implement circuit breaker pattern for external APIs"

---

## Incident Investigation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    OUTAGESHIELD AI WORKFLOW                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ CloudWatch  │     │   X-Ray     │     │ CloudTrail  │     │ AWS Config  │
  │   Alarms    │     │   Traces    │     │   Events    │     │   Changes   │
  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
         │                   │                   │                   │
         └───────────────────┴─────────┬─────────┴───────────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │      EventBridge       │
                          │    (Event Ingestion)   │
                          └───────────┬────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 0: DETECTION                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-detection-dev                                                                 │ │
│  │  • Parse CloudWatch alarm event                                                             │ │
│  │  • Create incident record in DynamoDB                                                       │ │
│  │  • Index event in OpenSearch                                                                │ │
│  │  • Trigger Step Functions workflow                                                          │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: CORRELATION                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-correlation-dev                                                               │ │
│  │  • Query related alarms (same service, time window)                                         │ │
│  │  • Fetch recent deployments from DynamoDB                                                   │ │
│  │  • Fetch config changes from DynamoDB                                                       │ │
│  │  • Query past incidents for the service                                                     │ │
│  │  • Build correlation context object                                                         │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: SEVERITY SCORING                                                                        │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-scoring-dev                                                                   │ │
│  │  • Call Bedrock AI to analyze business impact                                               │ │
│  │  • Calculate severity score (1-5: Info, Low, Medium, Warning, Critical)                     │ │
│  │  • Calculate business impact score (1-10)                                                   │ │
│  │  • Estimate affected users and revenue at risk                                              │ │
│  │  • Generate AI reasoning for scoring decision                                               │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │  Severity >= 4?       │
                          └───────────┬───────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │ YES                               │ NO
                    ▼                                   │
┌───────────────────────────────────┐                   │
│  STEP 2b: ESCALATION              │                   │
│  ┌─────────────────────────────┐  │                   │
│  │ outageshield-notification   │  │                   │
│  │ • Send SNS escalation alert │  │                   │
│  │ • Notify SRE team           │  │                   │
│  └─────────────────────────────┘  │                   │
└───────────────────────────────────┘                   │
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: ROOT CAUSE ANALYSIS                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-rootcause-dev                                                                 │ │
│  │  • Call Bedrock AI with incident context                                                    │ │
│  │  • Identify primary root cause with confidence score                                        │ │
│  │  • Classify into category: capacity | performance | configuration | deployment | dependency │ │
│  │  • Extract supporting evidence                                                              │ │
│  │  • Return up to 3 ranked root causes                                                        │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 3b: BEDROCK AGENT INVESTIGATION                                                            │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-agent-invoker-dev → outageshield-agent-actions-dev                            │ │
│  │                                                                                             │ │
│  │  The AI agent autonomously calls 6 investigation tools:                                     │ │
│  │                                                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                             │ │
│  │  │ 1. searchLogs   │  │ 2. getRunbook   │  │ 3. checkDeploy  │                             │ │
│  │  │ OpenSearch logs │  │ DynamoDB        │  │ DynamoDB        │                             │ │
│  │  │ Error patterns  │  │ Runbook steps   │  │ Recent deploys  │                             │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                             │ │
│  │                                                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                             │ │
│  │  │ 4. searchTraces │  │ 5. checkConfig  │  │ 6. searchHist   │                             │ │
│  │  │ AWS X-Ray       │  │ AWS Config      │  │ DynamoDB        │                             │ │
│  │  │ Latency/errors  │  │ Drift detection │  │ Past incidents  │                             │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                             │ │
│  │                                                                                             │ │
│  │  Output: Comprehensive investigation report with findings from all tools                    │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: REMEDIATION RECOMMENDATIONS                                                             │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-remediation-recommend-dev                                                     │ │
│  │                                                                                             │ │
│  │  Generate 9 data-driven recommendations (anti-hallucination rules enforced):                │ │
│  │                                                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────┐   │ │
│  │  │ #1 Runbook        │ #2 Scaling       │ #3 Rollback      │ #4 Config Change │        │   │ │
│  │  │ From runbook DB   │ From log patterns│ From deployments │ From config drift│        │   │ │
│  │  ├─────────────────────────────────────────────────────────────────────────────────────┤   │ │
│  │  │ #5 Past Incidents │ #6 X-Ray Traces  │ #7 Log Errors    │ #8 Manual        │ #9 ... │   │ │
│  │  │ From history      │ From traces      │ From OpenSearch  │ Intervention     │        │   │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                                             │ │
│  │  Each recommendation includes: confidence %, risk level, TTR estimate, data source         │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 4b: AI SUMMARY GENERATION                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-remediation-summary-dev                                                       │ │
│  │  • Select best recommendation based on confidence and effectiveness                         │ │
│  │  • Generate AI-powered technical summary using Bedrock                                      │ │
│  │  • Create quick action AWS CLI commands                                                     │ │
│  │  • Extract investigation summary metrics                                                    │ │
│  │  • Store in outageshield-ai-reasoning-dev table                                             │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │ Auto-remediation      │
                          │ enabled?              │
                          └───────────┬───────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │ YES                               │ NO
                    ▼                                   │
┌───────────────────────────────────┐                   │
│  STEP 5: WAIT FOR APPROVAL        │                   │
│  ┌─────────────────────────────┐  │                   │
│  │ waitForTaskToken pattern    │  │                   │
│  │ • Create approval request   │  │                   │
│  │ • Wait for human approval   │  │                   │
│  │ • Timeout after 24 hours    │  │                   │
│  └─────────────────────────────┘  │                   │
└───────────────────────────────────┘                   │
                    │                                   │
                    ▼                                   │
┌───────────────────────────────────┐                   │
│  STEP 6: EXECUTE REMEDIATION      │                   │
│  ┌─────────────────────────────┐  │                   │
│  │ outageshield-remediation-   │  │                   │
│  │ executor-dev                │  │                   │
│  │ • Execute via SSM           │  │                   │
│  │ • Run approved action       │  │                   │
│  └─────────────────────────────┘  │                   │
└───────────────────────────────────┘                   │
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: TICKET CREATION                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-ticket-dev                                                                    │ │
│  │                                                                                             │ │
│  │  ┌─────────────────────┐              ┌─────────────────────┐                              │ │
│  │  │       JIRA          │              │     PagerDuty       │                              │ │
│  │  │  • Create ticket    │              │  • Create incident  │                              │ │
│  │  │  • Set priority     │              │  • Assign on-call   │                              │ │
│  │  │  • Add description  │              │  • Set urgency      │                              │ │
│  │  │  • Link to incident │              │  • Add details      │                              │ │
│  │  └─────────────────────┘              └─────────────────────┘                              │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 8: NOTIFICATIONS                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-notification-dev                                                              │ │
│  │                                                                                             │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                             │ │
│  │  │   SNS    │    │  Slack   │    │  Email   │    │   SMS    │                             │ │
│  │  │  Topic   │    │ Webhook  │    │  Alert   │    │  Alert   │                             │ │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘                             │ │
│  │                                                                                             │ │
│  │  Notification includes: Service, Severity, Root Cause, Revenue at Risk, Ticket Links       │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  STEP 9: POSTMORTEM GENERATION                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  outageshield-postmortem-dev                                                                │ │
│  │                                                                                             │ │
│  │  AI-generated postmortem includes:                                                          │ │
│  │  • Executive Summary                    • Timeline of events                                │ │
│  │  • Impact Analysis (users, revenue)     • Root Cause (with category)                        │ │
│  │  • Investigation Findings               • Remediation Actions Taken                         │ │
│  │  • AI Prevention Recommendations (5 steps based on RCA category)                            │ │
│  │  • Lessons Learned                                                                          │ │
│  │                                                                                             │ │
│  │  Prevention recommendations by category:                                                    │ │
│  │  ┌────────────┬────────────┬────────────┬────────────┬────────────┐                        │ │
│  │  │  capacity  │performance │   config   │ deployment │ dependency │                        │ │
│  │  │ Auto-scale │ Caching    │ Validation │ Canary     │ Circuit    │                        │ │
│  │  │ Planning   │ Optimize   │ IaC        │ Rollback   │ Breakers   │                        │ │
│  │  └────────────┴────────────┴────────────┴────────────┴────────────┘                        │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │   WORKFLOW COMPLETE   │
                          │   Status: Mitigating  │
                          └───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME DASHBOARD                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  React Dashboard (CloudFront + S3)                                                          │ │
│  │                                                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────┐   │ │
│  │  │  Incident: INC-6686982D  │  Service: email-service  │  SEV-4  │  🔴 capacity       │   │ │
│  │  ├─────────────────────────────────────────────────────────────────────────────────────┤   │ │
│  │  │  Root Cause: Database connection pool exhaustion (90% confidence)                   │   │ │
│  │  │  Affected Users: 600,000  │  Revenue at Risk: $3,420/hour                           │   │ │
│  │  ├─────────────────────────────────────────────────────────────────────────────────────┤   │ │
│  │  │  Recommendations (9)  │  AI Summary  │  Investigation  │  Quick Actions            │   │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                                             │ │
│  │  WebSocket: Real-time updates as workflow progresses                                        │ │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              OutageShield AI Architecture                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  CloudWatch  │    │    X-Ray     │    │  CloudTrail  │    │  AWS Config  │  │
│  │   Metrics    │    │   Traces     │    │    Events    │    │   Changes    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │                   │          │
│         └───────────────────┴───────────────────┴───────────────────┘          │
│                                     │                                           │
│                          ┌──────────▼──────────┐                               │
│                          │   EventBridge       │                               │
│                          │   (Ingestion)       │                               │
│                          └──────────┬──────────┘                               │
│                                     │                                           │
│                          ┌──────────▼──────────┐                               │
│                          │  Detection Lambda   │                               │
│                          │  (Anomaly Detection)│                               │
│                          └──────────┬──────────┘                               │
│                                     │                                           │
│                          ┌──────────▼──────────┐                               │
│                          │   Step Functions    │                               │
│                          │  (11-Step Workflow) │                               │
│                          └──────────┬──────────┘                               │
│                                     │                                           │
│    ┌────────────────────────────────┼────────────────────────────────┐         │
│    │                                │                                │         │
│    ▼                                ▼                                ▼         │
│ ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐      │
│ │Correlation│  │ Scoring  │  │   Bedrock    │  │Remediation│  │  Summary │      │
│ │  Lambda   │  │  Lambda  │  │    Agent     │  │  Lambda   │  │  Lambda  │      │
│ └──────────┘  └──────────┘  │  (6 Tools)   │  └──────────┘  └──────────┘      │
│                             └──────────────┘                                   │
│                                     │                                           │
│    ┌────────────────────────────────┼────────────────────────────────┐         │
│    │                                │                                │         │
│    ▼                                ▼                                ▼         │
│ ┌──────────┐              ┌──────────────┐              ┌──────────────┐       │
│ │ DynamoDB │              │  OpenSearch  │              │     SNS      │       │
│ │ (Storage)│              │  Serverless  │              │(Notifications)│       │
│ └──────────┘              └──────────────┘              └──────────────┘       │
│                                                                                 │
│                          ┌──────────────────┐                                  │
│                          │   CloudFront     │                                  │
│                          │   + S3 (UI)      │                                  │
│                          └────────┬─────────┘                                  │
│                                   │                                            │
│                          ┌────────▼─────────┐                                  │
│                          │  React Dashboard │                                  │
│                          │  (Incident Mgmt) │                                  │
│                          └──────────────────┘                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Incident Investigation Workflow

The Step Functions workflow executes an 11-step investigation process:

| Step | Lambda | Description |
|------|--------|-------------|
| 1 | `outageshield-correlation-dev` | Correlate context - gather logs, metrics, deployments |
| 2 | `outageshield-scoring-dev` | Score severity and business impact (1-5, 1-10) |
| 2b | `outageshield-notification-dev` | Send escalation alert if severity >= 4 |
| 3 | `outageshield-rootcause-dev` | AI root cause analysis via Bedrock with category |
| 3b | `outageshield-agent-invoker-dev` | Bedrock Agent deep investigation (6 tools) |
| 4 | `outageshield-remediation-recommend-dev` | Generate 9 remediation recommendations |
| 4b | `outageshield-remediation-summary-dev` | AI-powered summary with best action suggestion |
| 5 | Choice | Check if auto-remediation enabled |
| 6 | `outageshield-remediation-executor-dev` | Execute approved remediation (SSM) |
| 7 | `outageshield-ticket-dev` | Create Jira + PagerDuty tickets |
| 8 | `outageshield-notification-dev` | Send SNS notifications |
| 9 | `outageshield-postmortem-dev` | Generate AI postmortem with prevention recommendations |

---

## Real-World Example: Database Connection Pool Exhaustion

Here's a complete walkthrough of how OutageShield AI handles a real incident:

### Incident: `INC-6686982D`
- **Service**: `email-service`
- **Alarm**: `DatabaseConnections-email-service`
- **Trigger**: Database connection pool at 98% utilization

### Step 1: Detection & Correlation
CloudWatch alarm triggers detection. The correlation Lambda gathers context:
- **Related Alarms**: 5 correlated alarms detected
  - `DatabaseConnections-email-service` - Pool at 98%
  - `QueueBacklog-email-service` - Queue depth exceeded 36,589 messages
  - `Timeout-email-service` - Function timeout rate exceeded 100%
- **Deployments**: No recent deployments found
- **Config Changes**: None detected

### Step 2: Severity Scoring
AI analyzes business impact:
```
Severity Score: 4 (Warning)
Business Impact: 4/10
Affected Users: 600,000
Revenue at Risk: $3,420/hour (0.6% of hourly revenue)
SLA Status: Warning
```

**AI Reasoning**: "The email-service handles transactional emails for customer orders and account management. A disruption would impact order confirmations, password resets, and account notifications."

### Step 3: Root Cause Analysis
Bedrock AI identifies root causes with categories:

| Root Cause | Confidence | Category |
|------------|------------|----------|
| Database connection pool exhaustion due to increased load | 90% | 🔴 capacity |
| Inefficient database queries or excessive operations | 70% | 🟠 performance |
| Misconfiguration of connection pool settings | 80% | 🟡 configuration |

### Step 3b: Bedrock Agent Investigation
The AI agent uses 6 tools to investigate:

```
[Source: Incident History DB]
No past incidents found for email-service.

[Source: OpenSearch Logs]
Found 10 log entries:
- DBConnExhaustion-email-service: connections (586) > pool max (100)
- QueueBacklog-email-service: Queue depth exceeded 24,739 messages
- Timeout-email-service: Function timeout rate exceeded 84%

[Source: Runbook DB]
Runbook: "General Troubleshooting for DatabaseConnections"
Category: manual_intervention, TTR: 30-60 minutes
Steps: 5 steps available

[Source: Deployment History]
No recent deployments or config changes in last 24 hours.

[Source: X-Ray Traces]
Service: email-service | Requests: 0 | Errors: 0, Faults: 0
Note: X-Ray tracing may not be enabled.

[Source: AWS Config]
Auto-Scaling: Verify enabled [Check]
Connection Pool: Review limits [Check]
```

### Step 4: Remediation Recommendations
6 data-driven recommendations generated:

| # | Category | Description | Confidence | TTR |
|---|----------|-------------|------------|-----|
| 1 | manual_intervention | Runbook: "General Troubleshooting" with 5 steps | 85% | 15m |
| 2 | scaling | Logs: Latency threshold exceeded. Consider scaling. | 80% | 20m |
| 3 | manual_intervention | Config: Service configuration reviewed. No issues. | 65% | 10m |
| 4 | manual_intervention | X-Ray: No traces found. Enable X-Ray tracing. | 60% | 15m |
| 5 | manual_intervention | No recent deployments. Issue not deployment-related. | 60% | 10m |
| 6 | manual_intervention | No similar past incidents. New issue type. | 50% | 60m |

### Step 4b: AI Summary
```
Recommended Action: SCALING (80% confidence, ~20m TTR)

AI Summary: "The email-service experienced database connection pool exhaustion 
due to increased load, leading to high latency and triggered threshold alarms. 
Evidence indicates P99 latency anomalies and error spikes, with no recent 
deployments or configuration changes. Recommended action: scale the email-service 
to handle increased load."
```

**Quick Actions Generated**:
- 📖 Runbook Step 1: Check CloudWatch metrics for anomalies
- 🚀 SCALE OUT: `aws autoscaling set-desired-capacity --auto-scaling-group-name email-service-asg --desired-capacity 4`
- 🔬 X-Ray: Get fault traces for email-service
- 🚨 Check Alarm: QueueBacklog-email-service

### Step 7: Ticket Creation
- **Jira**: `TGSHLD-3112` - https://corpinfollc.atlassian.net/browse/TGSHLD-3112 (clickable in UI)
- **PagerDuty**: `Q0KCKCOX6887Q1` - Incident created and assigned

### Step 8: Notifications
SNS escalation sent to `sre-team@shopsphere.com`:
```
[OutageShield] SEV-4 | email-service | DatabaseConnections-email-service

Service:         email-service
Severity:        SEV-4
Root Cause:      Database connection pool exhaustion due to increased load
Revenue at Risk: $3,420/hour
Affected Users:  600,000
Jira Ticket:     TGSHLD-3112
```

### Step 9: Postmortem Generation
AI generates postmortem with prevention recommendations based on RCA category (capacity):
- Implement proactive capacity planning with 30% headroom
- Configure auto-scaling policies for database connections
- Add CloudWatch alarms for connection pool utilization at 70%
- Implement connection pooling best practices
- Schedule regular load testing

---

## Bedrock Agent Investigation Tools

The AI agent uses 6 specialized tools for comprehensive incident investigation:

| Tool | Description | Data Source |
|------|-------------|-------------|
| `searchIncidentHistory` | Find similar past incidents | DynamoDB |
| `searchLogs` | Query error patterns and anomalies | OpenSearch Serverless |
| `getRunbook` | Look up remediation runbook | DynamoDB (runbooks table) |
| `checkDeployments` | Check recent deployments and config changes | DynamoDB (deployments table) |
| `searchTraces` | Query latency and error traces | AWS X-Ray |
| `checkConfigDrift` | Check compliance issues and drift | AWS Config |

---

## AI Summary Generation

The Summary Lambda (`outageshield-remediation-summary`) generates actionable summaries after remediation recommendations:

### Features
- **Best Recommendation Selection** - Analyzes all recommendations and selects the most effective one
- **AI-Powered Summary** - Uses Bedrock to generate developer-focused technical summaries
- **Quick Action Commands** - Provides ready-to-run AWS CLI commands based on recommendation type
- **Investigation Summary** - Extracts key metrics and findings from agent investigation
- **Recommendation Breakdown** - Categorizes recommendations by type (scaling, rollback, config, manual)

### Quick Actions by Category

| Category | Example Commands |
|----------|------------------|
| **Scaling** | Scale ASG, check CPU/memory, view target group health |
| **Rollback** | List deployments, rollback to previous, stop deployment |
| **Configuration** | List/update SSM parameters, force service restart |
| **Manual** | Tail logs, search errors, check alarms, get X-Ray traces |

### Anti-Hallucination Rules

The remediation system enforces strict data-driven recommendations:

1. **X-Ray Traces**: If 0 requests traced → "No traces found. Enable X-Ray tracing" (never claims "healthy")
2. **Log Analysis**: Only reports actual error patterns found (no false 5xx claims)
3. **Deployment Check**: Reports actual deployment count and config changes from DynamoDB
4. **Runbook Steps**: Accurately counts steps from runbook content
5. **Past Incidents**: Reports actual count of similar incidents found
6. **Config Drift**: Reports actual compliance status from AWS Config

All 9 recommendations include:
- Data source attribution (e.g., "[Source: OpenSearch Logs]")
- Confidence percentage based on evidence strength
- Risk level (low/medium/high)
- Estimated time to resolution (TTR)

---

## Postmortem Generation

The Postmortem Lambda (`outageshield-postmortem-dev`) automatically generates comprehensive incident reports:

### Postmortem Contents
- **Executive Summary** - AI-generated overview of the incident
- **Timeline** - Key events from detection to resolution
- **Impact Analysis** - Affected users, revenue impact, duration
- **Root Cause** - Categorized root cause with confidence score
- **Investigation Findings** - Summary of agent tool findings
- **Remediation Actions** - Actions taken to resolve the incident
- **Prevention Recommendations** - AI-generated long-term prevention steps (5 specific recommendations based on RCA category)
- **Lessons Learned** - Key takeaways for future incidents

### Prevention Recommendation Categories
| RCA Category | Prevention Focus Areas |
|--------------|----------------------|
| **capacity** | Auto-scaling policies, capacity planning, resource monitoring, load testing |
| **performance** | Query optimization, caching strategies, performance testing, SLO tuning |
| **configuration** | Config validation, IaC adoption, change management, config drift detection |
| **deployment** | CI/CD improvements, canary deployments, rollback automation, feature flags |
| **dependency** | Circuit breakers, fallback mechanisms, dependency health checks, SLA monitoring |

---

## CloudFormation Stacks

The infrastructure is deployed across 15 CloudFormation stacks:

| Stack | File | Description |
|-------|------|-------------|
| 01 | `01-ingestion-stack.yaml` | EventBridge rules, Kinesis streams for data ingestion |
| 02 | `02-storage-stack.yaml` | DynamoDB tables, OpenSearch Serverless collection |
| 03 | `03-detection-stack.yaml` | Detection Lambda, CloudWatch alarm processing |
| 04 | `04-correlation-stack.yaml` | Correlation Lambda, context gathering |
| 05 | `05-reasoning-stack.yaml` | RCA, Scoring, Remediation, Postmortem Lambdas |
| 06 | `06-orchestration-stack.yaml` | Step Functions workflow (11-step investigation) |
| 07 | `07-notifications-stack.yaml` | SNS topics, notification Lambda, ticket creation |
| 08 | `08-remediation-stack.yaml` | SSM remediation executor, approval workflow |
| 09 | `09-dashboard-stack.yaml` | API Gateway REST API, dashboard Lambda |
| 10 | `10-auth-stack.yaml` | Cognito user pool, authentication |
| 11 | `11-websocket-stack.yaml` | WebSocket API for real-time updates |
| 12 | `12-cloudfront-stack.yaml` | CloudFront distribution, S3 bucket for UI |
| 13 | `13-bedrock-agent-stack.yaml` | Bedrock Agent, agent actions Lambda (6 tools) |
| 14 | `14-cloudtrail-deployments-stack.yaml` | CloudTrail for deployment tracking |
| 15 | `15-xray-config-stack.yaml` | X-Ray tracing, AWS Config integration |

---

## Lambda Functions

| Lambda | Description | Key Features |
|--------|-------------|--------------|
| `outageshield-detection-dev` | Anomaly detection | Processes CloudWatch alarms, creates incidents, writes to OpenSearch |
| `outageshield-correlation-dev` | Context correlation | Gathers logs, metrics, deployments from multiple sources |
| `outageshield-scoring-dev` | Severity scoring | Calculates severity (1-5) and business impact (1-10) |
| `outageshield-rootcause-dev` | Root cause analysis | AI-powered RCA with 5 category classifications |
| `outageshield-agent-invoker-dev` | Bedrock agent orchestration | Invokes agent with 6 investigation tools |
| `outageshield-agent-actions-dev` | Agent tool execution | Executes searchLogs, checkDeployments, searchTraces, etc. |
| `outageshield-remediation-recommend-dev` | Recommendation generation | 9 data-driven recommendations with anti-hallucination rules |
| `outageshield-remediation-summary-dev` | AI summary | Best action selection, quick commands, investigation summary |
| `outageshield-remediation-executor-dev` | Remediation execution | Executes approved actions via SSM |
| `outageshield-postmortem-dev` | Postmortem generation | AI prevention recommendations based on RCA category |
| `outageshield-notification-dev` | Notifications | SNS, Slack, PagerDuty alerts, escalation |
| `outageshield-ticket-dev` | Ticket creation | Jira and ServiceNow integration |
| `outageshield-dashboard-api-dev` | Dashboard API | REST API for UI, incident CRUD operations |

---

## Project Structure

```
OutageShield AI/
├── UI/                          # React Dashboard
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── hooks/               # Custom React hooks
│   │   ├── pages/               # Page components
│   │   │   ├── Dashboard.tsx    # Main incident dashboard
│   │   │   ├── IncidentDetail.tsx  # Incident details with RCA badges
│   │   │   ├── Incidents.tsx    # Incidents list
│   │   │   ├── Login.tsx        # Authentication
│   │   │   ├── Notifications.tsx
│   │   │   ├── PagerDutyDetail.tsx
│   │   │   ├── Postmortems.tsx  # Postmortem list and details
│   │   │   ├── SnsDetail.tsx
│   │   │   └── TicketDetail.tsx
│   │   ├── services/
│   │   │   ├── api.ts           # API client
│   │   │   └── websocket.ts     # Real-time updates
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── stacks/                      # CloudFormation Stacks (15 stacks)
│   ├── 01-ingestion-stack.yaml      # EventBridge, Kinesis
│   ├── 02-storage-stack.yaml        # DynamoDB, OpenSearch
│   ├── 03-detection-stack.yaml      # Detection Lambda
│   ├── 04-correlation-stack.yaml    # Correlation Lambda
│   ├── 05-reasoning-stack.yaml      # RCA, Scoring, Remediation, Postmortem
│   ├── 06-orchestration-stack.yaml  # Step Functions workflow
│   ├── 07-notifications-stack.yaml  # SNS, Ticket creation
│   ├── 08-remediation-stack.yaml    # SSM remediation executor
│   ├── 09-dashboard-stack.yaml      # API Gateway
│   ├── 10-auth-stack.yaml           # Cognito authentication
│   ├── 11-websocket-stack.yaml      # WebSocket API
│   ├── 12-cloudfront-stack.yaml     # CloudFront + S3
│   ├── 13-bedrock-agent-stack.yaml  # Bedrock Agent + Action Lambda
│   ├── 14-cloudtrail-deployments-stack.yaml  # CloudTrail deployment tracking
│   ├── 15-xray-config-stack.yaml    # X-Ray + Config integration
│   ├── stepfunctions/               # Step Functions definitions
│   │   ├── incident-workflow.asl.json  # Main workflow definition
│   │   ├── approval-lambda.py          # Approval handler
│   │   └── README.md
│   ├── deploy.sh
│   └── README.md
│
├── scripts/
│   ├── lambdas/                 # Lambda deployment scripts
│   │   └── update-postmortem-lambda.py       # AI prevention recommendations
│   │
│   ├── servicenow/              # ServiceNow integration scripts (11 scripts)
│   │   ├── configure-servicenow-instance.py  # Configure ServiceNow instance
│   │   ├── create-servicenow-sync-lambda.py  # Sync Lambda for ServiceNow
│   │   ├── create-servicenow-ui.py           # ServiceNow UI components
│   │   ├── deploy-servicenow-poller.py       # Deploy approval poller Lambda
│   │   ├── fix-data.py                       # Fix ServiceNow data
│   │   ├── fix-ui-page.py                    # Fix ServiceNow UI page
│   │   ├── setup-servicenow-complete.py      # Complete setup script
│   │   ├── setup-servicenow-integration.py   # Integration setup
│   │   ├── sync-servicenow-status.py         # Sync status with ServiceNow
│   │   ├── test-servicenow-credentials.py    # Test credentials
│   │   └── update-servicenow-urls.py         # Update ServiceNow URLs
│   │
│   ├── tests/                   # Test and verification scripts (5 scripts)
│   │   ├── full-workflow-test.py             # End-to-end workflow test
│   │   ├── test-approval-flow.py             # Test approval workflow
│   │   ├── test-e2e-with-servicenow.py       # E2E test with ServiceNow
│   │   ├── test-full-servicenow-flow.py      # Full ServiceNow flow test
│   │   └── test-servicenow-integration.py    # ServiceNow integration test
│   │
│   ├── check-incident.py        # Check incident details
│   ├── check-postmortems.py     # Check postmortem data
│   ├── check-servicenow.py      # Check ServiceNow status
│   ├── check-status.py          # Check system status
│   ├── check-tickets.py         # Match Jira tickets to incidents
│   ├── cleanup-postmortems.py   # Clean up duplicate postmortems
│   ├── display-all-db-data.py   # Display all DynamoDB data
│   ├── rerun-lambdas.py         # Rerun Lambdas for incidents
│   ├── trigger-6-incidents.py   # Trigger 6 test incidents
│   └── trigger-detection.py     # Trigger detection Lambda
│
├── dashboard-api-code/          # Dashboard API Lambda
│   └── index.py
│
├── docs/
│   ├── continuous-learning.md       # Continuous learning documentation
│   ├── data-ingestion-guide.md      # Data ingestion guide
│   ├── lambda-stack-alignment.md    # Lambda-stack mapping reference
│   └── servicenow-setup.md          # ServiceNow integration guide
│
└── README.md
```

---

## Technology Stack

### Backend (AWS)
- **Compute**: AWS Lambda (Python 3.12)
- **Orchestration**: AWS Step Functions
- **AI/ML**: Amazon Bedrock (Claude 3 Haiku)
- **Storage**: Amazon DynamoDB, OpenSearch Serverless
- **Messaging**: Amazon SNS, EventBridge
- **Tracing**: AWS X-Ray
- **Compliance**: AWS Config
- **API**: Amazon API Gateway (REST + WebSocket)
- **CDN**: Amazon CloudFront
- **Auth**: Amazon Cognito

### Frontend
- **Framework**: React 18.3 with TypeScript
- **Build**: Vite 5.3
- **Styling**: Tailwind CSS 3.4
- **Charts**: Recharts
- **Icons**: Lucide React
- **Routing**: React Router 6

### Integrations
- **Ticketing**: Jira (TGSHLD project at corpinfollc.atlassian.net), ServiceNow (with custom UI and approval workflow)
- **Alerting**: PagerDuty
- **Notifications**: SNS (sre-team@shopsphere.com), Slack, Email, SMS

---

## DynamoDB Tables

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `outageshield-incidents-dev` | `incident_id` | Active and historical incidents |
| `outageshield-events-dev` | `event_id` | Detection events |
| `outageshield-runbooks-dev` | `runbook_id` | Remediation runbooks |
| `outageshield-deployments-dev` | `deployment_id` | Deployment history (GSI: service-timestamp) |
| `outageshield-postmortems-dev` | `postmortem_id` | Generated postmortems |
| `outageshield-workflow-state-dev` | `workflow_id` | Workflow execution state |
| `outageshield-approvals-dev` | `approval_id` | Human approval requests |
| `outageshield-ai-reasoning-dev` | `incident_id` | AI reasoning, summary, and recommendations |

---

## Runbook Types

The system includes 9 pre-configured runbooks:

| Runbook ID | Title | Category |
|------------|-------|----------|
| `HighLatency` | High Latency Troubleshooting | scaling |
| `High5xxRate` | 5xx Error Rate Troubleshooting | rollback |
| `HighCPU` | High CPU Utilization | scaling |
| `MemoryPressure` | Memory Pressure Troubleshooting | configuration_change |
| `ConnectionPool` | Database Connection Pool Exhaustion | configuration_change |
| `QueueBacklog` | Message Queue Backlog | scaling |
| `AuthFailures` | Authentication Failures | manual_intervention |
| `CacheMissRate` | High Cache Miss Rate | configuration_change |
| `DiskUsage` | Disk Usage Critical | configuration_change |

---

## SNS Topics and Notifications

OutageShield uses 3 SNS topics for notifications:

| Topic | Purpose | Subscriber |
|-------|---------|------------|
| `outageshield-alerts-dev` | General incident alerts | sre-team@shopsphere.com |
| `outageshield-approvals-dev` | Approval request notifications | sre-team@shopsphere.com |
| `outageshield-escalation-dev` | High-severity escalations (SEV >= 4) | sre-team@shopsphere.com |

### Notification Content
Escalation notifications include:
- Service name and severity level
- Root cause with confidence score
- Revenue at risk and affected users
- Jira ticket link (clickable)
- Quick action recommendations

---

## Jira Integration

OutageShield automatically creates Jira tickets in the **TGSHLD** project:

- **Project**: TGSHLD (corpinfollc.atlassian.net)
- **Ticket Format**: `TGSHLD-XXXX`
- **URL Pattern**: `https://corpinfollc.atlassian.net/browse/TGSHLD-XXXX`

### Ticket Contents
- Summary: Service name + alarm type
- Description: Root cause, severity, affected users, revenue at risk
- Priority: Mapped from severity score (1-5)
- Labels: Service name, RCA category

### UI Integration
The dashboard displays clickable Jira ticket links that open directly in Atlassian.

---

## Testing Scripts

### Trigger Test Incidents

```bash
# Trigger 6 different test incidents
python scripts/trigger-6-incidents.py

# Incidents triggered:
# 1. HighLatency-payment-gateway
# 2. DatabaseConnections-order-db
# 3. ErrorRate-checkout-service
# 4. CPUUtilization-search-cluster
# 5. QueueBacklog-notification-service
# 6. MemoryPressure-inventory-cache
```

### Rerun Lambdas for Existing Incidents

```bash
# Rerun all Lambdas for specific incidents
python scripts/rerun-lambdas.py INC-XXXXXXXX

# Rerun for all incidents
python scripts/rerun-lambdas.py --all
```

### Check and Clean Data

```bash
# Display all DynamoDB data
python scripts/display-all-db-data.py

# Check Jira tickets and match to incidents
python scripts/check-tickets.py

# Clean up duplicate postmortems
python scripts/cleanup-postmortems.py
```

---

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm
- Python 3.12+
- AWS account with Bedrock access enabled

### Deploy Infrastructure

```bash
# Deploy all CloudFormation stacks
cd stacks
./deploy.sh dev

# Or deploy individual stacks
aws cloudformation deploy \
  --template-file 02-storage-stack.yaml \
  --stack-name outageshield-storage-dev \
  --capabilities CAPABILITY_NAMED_IAM
```

### Deploy Lambda Code

```bash
# Deploy detection Lambda
python scripts/lambdas/update-detection-opensearch.py

# Deploy correlation Lambda
python scripts/lambdas/update-correlation-lambda.py

# Deploy scoring Lambda
python scripts/lambdas/update-scoring-lambda.py

# Deploy RCA Lambda (with category classification)
python scripts/lambdas/update-rca-lambda-v2.py

# Deploy agent invoker Lambda
python scripts/lambdas/update-agent-invoker.py

# Deploy agent actions Lambda (6 tools)
python scripts/lambdas/update-agent-actions-all-tools.py

# Deploy remediation Lambda (9 recommendations)
python scripts/lambdas/update-remediation-lambda2.py

# Deploy summary Lambda (AI summary generation)
python scripts/lambdas/create-summary-lambda.py

# Deploy postmortem Lambda (AI prevention recommendations)
python scripts/lambdas/update-postmortem-lambda.py
```

### Build and Deploy UI

```bash
cd UI

# Install dependencies
npm install

# Build for production
npm run build

# Deploy to S3
aws s3 sync dist/ s3://outageshield-ui-dev/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E2T6I7E13WD75Y \
  --paths "/*"
```

### Seed Sample Data

```bash
# Generate test incidents (creates 100 incidents across 15 services)
# Note: Run from project root
python scripts/tests/full-workflow-test.py
```

---

## Testing

### Test Scripts

```bash
# Full end-to-end workflow test
python scripts/tests/full-workflow-test.py

# Test approval workflow
python scripts/tests/test-approval-flow.py

# Test ServiceNow integration
python scripts/tests/test-servicenow-integration.py

# Full ServiceNow flow test
python scripts/tests/test-full-servicenow-flow.py

# End-to-end test with ServiceNow
python scripts/tests/test-e2e-with-servicenow.py
```

### ServiceNow Integration Scripts

```bash
# Test ServiceNow credentials
python scripts/servicenow/test-servicenow-credentials.py

# Deploy ServiceNow approval poller Lambda
python scripts/servicenow/deploy-servicenow-poller.py

# Setup ServiceNow integration
python scripts/servicenow/setup-servicenow-integration.py

# Complete ServiceNow setup
python scripts/servicenow/setup-servicenow-complete.py

# Configure ServiceNow instance
python scripts/servicenow/configure-servicenow-instance.py
```

### Verification Commands

```bash
# Check incident count
aws dynamodb scan --table-name outageshield-incidents-dev --select COUNT

# Check postmortem count
aws dynamodb scan --table-name outageshield-postmortems-dev --select COUNT

# View recent incidents
aws dynamodb scan --table-name outageshield-incidents-dev \
  --projection-expression "incident_id,service,#s,severity_score" \
  --expression-attribute-names '{"#s":"status"}' \
  --max-items 10
```

---

## Configuration

### Environment Variables

**UI (.env.local)**
```env
VITE_API_URL=https://your-api-gateway-url/dev
VITE_WS_URL=wss://your-websocket-url/dev
VITE_COGNITO_USER_POOL_ID=us-east-1_xxxxx
VITE_COGNITO_CLIENT_ID=xxxxx
```

**Lambda Environment Variables**
- `INCIDENTS_TABLE`: DynamoDB incidents table name
- `EVENTS_TABLE`: DynamoDB events table name
- `RUNBOOKS_TABLE`: DynamoDB runbooks table name
- `DEPLOYMENTS_TABLE`: DynamoDB deployments table name
- `OPENSEARCH_ENDPOINT`: OpenSearch Serverless endpoint
- `AGENT_ID`: Bedrock Agent ID
- `MODEL_ID`: Bedrock model ID (anthropic.claude-3-haiku-20240307-v1:0)

---

## API Endpoints

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/incidents` | List all incidents |
| GET | `/incidents/{id}` | Get incident details |
| GET | `/incidents/{id}/timeline` | Get incident timeline |
| GET | `/risk` | Get service risk levels |
| GET | `/postmortems` | List postmortems |
| GET | `/postmortems/{id}` | Get postmortem details |
| POST | `/approve/{id}` | Approve/reject remediation |
| GET | `/stats` | Dashboard statistics |

### WebSocket API

| Action | Description |
|--------|-------------|
| `subscribe` | Subscribe to incident updates |
| `incident_update` | Real-time incident status changes |

---

## Incident Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│  Detected   │ ──▶ │ Investigating│ ──▶ │ Mitigating │ ──▶ │ Resolved │
└─────────────┘     └──────────────┘     └────────────┘     └──────────┘
      │                    │                   │                  │
      │                    │                   │                  │
      ▼                    ▼                   ▼                  ▼
   Signal              RCA + Agent        Remediation        Postmortem
   Generated           Investigation       Executed          Generated
                            │
                            ▼
                       AI Summary
                       Generated
```

### Workflow States

| State | Description |
|-------|-------------|
| `investigating` | Initial state, correlation and RCA in progress |
| `awaiting_approval` | Human approval required for remediation |
| `executing` | Remediation action being executed |
| `mitigating` | Remediation complete, monitoring for resolution |
| `resolved` | Incident fully resolved |
| `degraded` | Workflow completed with errors |

---

## Monitoring

### CloudWatch Dashboards
- Lambda execution metrics
- Step Functions execution status
- API Gateway latency and errors
- DynamoDB read/write capacity

### X-Ray Tracing
- End-to-end request tracing
- Lambda cold start analysis
- Downstream dependency mapping

### Alarms
- High error rate alerts
- Latency threshold breaches
- DynamoDB throttling

---

## Security

- **Authentication**: Amazon Cognito user pools
- **Authorization**: IAM roles with least-privilege policies
- **Encryption**: 
  - Data at rest: DynamoDB encryption, S3 SSE
  - Data in transit: TLS 1.2+
- **Network**: VPC endpoints for AWS services
- **Secrets**: AWS Secrets Manager for API keys

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is proprietary software developed for Rackspace Inc.

---

## Support

For questions or issues, contact the Cloud Operations team.

**Dashboard URL**: https://d2k1km1tzlio49.cloudfront.net

---

## Acknowledgments

- Amazon Web Services for cloud infrastructure
- Anthropic for Claude AI models via Amazon Bedrock
- The open-source community for React, Vite, and Tailwind CSS
