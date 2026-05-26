# OutageShield AI

**AI-Powered Incident Detection, Correlation, and Remediation Platform for Enterprise Cloud Operations**

[![AWS](https://img.shields.io/badge/AWS-Cloud-orange)](https://aws.amazon.com)
[![Bedrock](https://img.shields.io/badge/Amazon-Bedrock-blue)](https://aws.amazon.com/bedrock/)
[![React](https://img.shields.io/badge/React-18.3-61dafb)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-blue)](https://www.typescriptlang.org)

---

## Overview

OutageShield AI is an enterprise-grade incident management platform that leverages Amazon Bedrock and AWS services to automatically detect, investigate, and remediate cloud infrastructure incidents. The system ingests operational data from multiple AWS sources, correlates alerts with deployment and configuration changes, identifies root causes using AI, and recommends or triggers remediation actions.

### Key Features

- **🔍 Early Outage Detection** - Detects anomalies in CloudWatch metrics, logs, and X-Ray traces before full service degradation
- **🤖 AI-Powered Root Cause Analysis** - Amazon Bedrock agent autonomously investigates incidents using 6 specialized tools
- **📊 Intelligent Correlation** - Links alerts with deployments, config changes, and historical incidents
- **💡 Smart Remediation** - Generates ranked remediation recommendations with runbook integration
- **🎫 Ticketing Integration** - Automatic Jira and PagerDuty ticket creation
- **📱 Real-time Dashboard** - React-based incident command center with WebSocket updates
- **📝 Auto-generated Postmortems** - AI-generated incident summaries and prevention recommendations

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
│                          │   (9-Step Workflow) │                               │
│                          └──────────┬──────────┘                               │
│                                     │                                           │
│    ┌────────────────────────────────┼────────────────────────────────┐         │
│    │                                │                                │         │
│    ▼                                ▼                                ▼         │
│ ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐      │
│ │Correlation│  │ Scoring  │  │   Bedrock    │  │Remediation│  │  Ticket  │      │
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

The Step Functions workflow executes a 9-step investigation process:

| Step | Lambda | Description |
|------|--------|-------------|
| 1 | `outageshield-correlation` | Correlate context - gather logs, metrics, deployments |
| 2 | `outageshield-scoring` | Score severity and business impact (1-5, 1-10) |
| 3 | `outageshield-rootcause` | AI root cause analysis via Bedrock |
| 3b | `outageshield-agent-invoker` | Bedrock Agent deep investigation (6 tools) |
| 4 | `outageshield-remediation-recommend` | Generate remediation recommendations |
| 5 | Choice | Check if auto-remediation enabled |
| 6 | `outageshield-remediation-executor` | Execute approved remediation (SSM) |
| 7 | `outageshield-ticket` | Create Jira + PagerDuty tickets |
| 8 | `outageshield-notification` | Send SNS notifications |
| 9 | `outageshield-postmortem` | Generate AI postmortem |

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

## Project Structure

```
OutageShield AI/
├── UI/                          # React Dashboard
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Page components
│   │   │   ├── Dashboard.tsx    # Main incident dashboard
│   │   │   ├── IncidentDetail.tsx
│   │   │   ├── Postmortems.tsx
│   │   │   └── ServiceRisk.tsx
│   │   ├── services/
│   │   │   ├── api.ts           # API client
│   │   │   └── websocket.ts     # Real-time updates
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── stacks/                      # CloudFormation Stacks
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
│   ├── 14-cloudtrail-deployments-stack.yaml
│   ├── 15-xray-config-stack.yaml    # X-Ray + Config integration
│   └── deploy.sh
│
├── scripts/
│   ├── lambdas/                 # Lambda deployment scripts
│   │   ├── add-xray-config-tools.py
│   │   ├── update-agent-invoker.py
│   │   ├── update-remediation-lambda2.py
│   │   ├── update-correlation-lambda.py
│   │   └── ...
│   ├── reset-with-real-data.py  # Seed data and trigger incidents
│   └── rebuild-layer.py         # Rebuild Lambda layers
│
├── dashboard-api-code/          # Dashboard API Lambda
│   └── index.py
│
├── docs/
│   ├── data-ingestion-guide.md
│   ├── continuous-learning.md
│   └── lambda-stack-alignment.md
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
- **Ticketing**: Jira, ServiceNow
- **Alerting**: PagerDuty
- **Notifications**: Slack, Email, SMS

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

---

## Runbook Types

The system includes 8 pre-configured runbooks:

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
# Deploy agent actions Lambda (6 tools)
python scripts/lambdas/add-xray-config-tools.py

# Deploy agent invoker Lambda
python scripts/lambdas/update-agent-invoker.py

# Deploy remediation Lambda
python scripts/lambdas/update-remediation-lambda2.py

# Deploy correlation Lambda
python scripts/lambdas/update-correlation-lambda.py
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
# Seed runbooks, deployments, and trigger test incidents
python scripts/reset-with-real-data.py
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
```

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
