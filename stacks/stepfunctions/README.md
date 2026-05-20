# OutageShield AI — Step Functions State Machine

## State Machine: Incident Investigation Workflow

### Visual Flow

```
┌──────────────────────┐
│  InitializeIncident  │  Create incident record in DynamoDB
│  (Task - DynamoDB)   │  Status: "investigating"
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌─────────────────────────────┐
│   CorrelateContext   │────▶│  HandleCorrelationFailure   │
│  (Task - Lambda)     │fail │  (Pass - partial context)   │
│  Timeout: 120s       │     └──────────────┬──────────────┘
│  Retry: 2x @ 5s     │                    │
└──────────┬───────────┘                    │
           │ success                        │
           ▼                                ▼
┌──────────────────────────────────────────────┐
│         UpdateDashboard_Correlation          │
│  (Task - DynamoDB) Push progress             │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────┐     ┌─────────────────────────────┐
│    ScoreIncident     │────▶│    HandleScoringFailure     │
│  (Task - Lambda)     │fail │  (Pass - defaults: 3/5)     │
│  Timeout: 30s        │     └──────────────┬──────────────┘
│  Retry: 2x @ 5s     │                    │
└──────────┬───────────┘                    │
           │ success                        │
           ▼                                ▼
┌──────────────────────────────────────────────┐
│            CheckEscalation                   │
│  (Choice)                                    │
│  severity >= 4? ──YES──▶ SendEscalationAlert │
│  severity < 4?  ──NO───▶ AnalyzeRootCause   │
└──────────────────────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
┌──────────────────────┐  ┌────────────────────┐
│ SendEscalationAlert  │  │                    │
│ (Task - Lambda)      │  │                    │
│ Notify on-call team  │  │                    │
└──────────┬───────────┘  │                    │
           │              │                    │
           └──────────────┘                    │
                       │                       │
                       ▼                       │
┌──────────────────────┐     ┌─────────────────────────────┐
│  AnalyzeRootCause    │────▶│      HandleRCAFailure       │
│  (Task - Lambda)     │fail │  (Pass - empty causes)      │
│  Timeout: 90s        │     └──────────────┬──────────────┘
│  Retry: 2x @ 5s     │                    │
└──────────┬───────────┘                    │
           │ success                        │
           ▼                                ▼
┌──────────────────────────────────────────────┐
│            UpdateDashboard_RCA               │
│  (Task - DynamoDB) Push progress             │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────┐     ┌─────────────────────────────┐
│ RecommendRemediation │────▶│  HandleRemediationFailure   │
│  (Task - Lambda)     │fail │  (Pass - empty recs)        │
│  Timeout: 60s        │     └──────────────┬──────────────┘
│  Retry: 2x @ 5s     │                    │
└──────────┬───────────┘                    │
           │ success                        │
           ▼                                ▼
┌──────────────────────────────────────────────┐
│          CheckAutoRemediation                │
│  (Choice)                                    │
│  auto_remediation = true? ──▶ RequestApproval│
│  auto_remediation = false? ─▶ CreateTicket   │
└──────────────────────────────────────────────┘
           │                       │
           ▼                       │
┌──────────────────────┐           │
│   RequestApproval    │           │
│  (Task - Lambda)     │           │
│  Send to approver    │           │
└──────────┬───────────┘           │
           │                       │
           ▼                       │
┌──────────────────────┐           │
│   WaitForApproval    │           │
│  (Wait - 60s)        │           │
└──────────┬───────────┘           │
           │                       │
           ▼                       │
┌──────────────────────┐     ┌─────────────────────────────┐
│  ExecuteRemediation  │────▶│   HandleExecutionFailure    │
│  (Task - Lambda)     │fail │  (Task - notify failure)    │
│  Timeout: 300s       │     └──────────────┬──────────────┘
│  Retry: 1x @ 10s    │                    │
└──────────┬───────────┘                    │
           │ success                        │
           └────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              CreateTicket                     │
│  (Choice)                                    │
│  severity >= 3? ──▶ InvokeTicketCreation     │
│  severity < 3?  ──▶ NotifyTeam              │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────┐
│ InvokeTicketCreation │
│  (Task - Lambda)     │
│  ServiceNow / Jira   │
│  Timeout: 60s        │
│  Retry: 3x @ 10s    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌─────────────────────────────┐
│     NotifyTeam       │────▶│  HandleNotificationFailure  │
│  (Task - Lambda)     │fail │  (Pass - escalate)          │
│  Timeout: 30s        │     └──────────────┬──────────────┘
│  Retry: 3x exp.     │                    │
└──────────┬───────────┘                    │
           │ success                        │
           ▼                                ▼
┌──────────────────────────────────────────────┐
│          UpdateDashboard_Notify              │
│  (Task - DynamoDB) Push progress             │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         DetermineWorkflowStatus              │
│  (Choice)                                    │
│  Any critical step failed? ──▶ Degraded      │
│  All steps OK?             ──▶ Resolved      │
└──────────┬───────────────────┬───────────────┘
           │                   │
           ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│ WorkflowResolved │  │ WorkflowDegraded │
│ (Task - DynamoDB)│  │ (Task - DynamoDB)│
│ status=mitigating│  │ status=investing │
│ workflow=resolved│  │ workflow=degraded│
│      END         │  │      END         │
└──────────────────┘  └──────────────────┘
```

## All States Summary

| # | State Name | Type | Purpose | Timeout | Retries |
|---|-----------|------|---------|---------|---------|
| 1 | `InitializeIncident` | Task (DynamoDB) | Create incident record, set status | — | — |
| 2 | `CorrelateContext` | Task (Lambda) | Build Incident Context from multiple sources | 120s | 2 |
| 3 | `HandleCorrelationFailure` | Pass | Record failure, produce partial context | — | — |
| 4 | `UpdateDashboard_Correlation` | Task (DynamoDB) | Push progress to dashboard | — | — |
| 5 | `ScoreIncident` | Task (Lambda) | Calculate Severity (1-5) and Business Impact (1-10) | 30s | 2 |
| 6 | `HandleScoringFailure` | Pass | Assign default scores (3/5) | — | — |
| 7 | `CheckEscalation` | Choice | Route to escalation if severity >= 4 | — | — |
| 8 | `SendEscalationAlert` | Task (Lambda) | Alert on-call team immediately | 30s | 2 |
| 9 | `AnalyzeRootCause` | Task (Lambda) | Bedrock root-cause analysis with confidence scores | 90s | 2 |
| 10 | `HandleRCAFailure` | Pass | Return empty causes with insufficient-data message | — | — |
| 11 | `UpdateDashboard_RCA` | Task (DynamoDB) | Push progress to dashboard | — | — |
| 12 | `RecommendRemediation` | Task (Lambda) | Generate ranked remediation recommendations | 60s | 2 |
| 13 | `HandleRemediationFailure` | Pass | Record failure, empty recommendations | — | — |
| 14 | `CheckAutoRemediation` | Choice | Route based on auto-remediation config | — | — |
| 15 | `RequestApproval` | Task (Lambda) | Send approval request to designated approver | 30s | — |
| 16 | `WaitForApproval` | Wait | Wait for human approval (60s demo) | 60s | — |
| 17 | `ExecuteRemediation` | Task (Lambda) | Execute via AWS Systems Manager | 300s | 1 |
| 18 | `HandleExecutionFailure` | Task (Lambda) | Notify team of execution failure | — | — |
| 19 | `CreateTicket` | Choice | Route to ticket creation if severity >= 3 | — | — |
| 20 | `InvokeTicketCreation` | Task (Lambda) | Create ServiceNow/Jira ticket | 60s | 3 |
| 21 | `NotifyTeam` | Task (Lambda) | Send alert to notification channels | 30s | 3 |
| 22 | `HandleNotificationFailure` | Pass | Record failure, mark for escalation | — | — |
| 23 | `UpdateDashboard_Notify` | Task (DynamoDB) | Push progress to dashboard | — | — |
| 24 | `DetermineWorkflowStatus` | Choice | Evaluate if workflow resolved or degraded | — | — |
| 25 | `WorkflowResolved` | Task (DynamoDB) | Mark incident as mitigating, workflow resolved | — | — |
| 26 | `WorkflowDegraded` | Task (DynamoDB) | Mark workflow as degraded, keep investigating | — | — |

## State Types Used

| Type | Count | Purpose |
|------|-------|---------|
| Task (Lambda) | 9 | Core processing — correlation, scoring, RCA, remediation, approval, execution, notifications |
| Task (Lambda .waitForTaskToken) | 1 | Human approval — pauses INDEFINITELY until callback |
| Task (DynamoDB) | 7 | Direct integrations — init, dashboard updates, final status |
| Choice | 4 | Routing — escalation, auto-remediation, ticket creation, final status |
| Pass | 6 | Error handling — record failures with default values |

**Total: 27 states**

## Human-in-the-Loop: Callback Token Pattern

The workflow is **fully sequential per incident**. When it hits the human approval gate, it **hangs indefinitely** — no ticket, no notification — until the approver responds. The UI shows "Awaiting Approval" for that incident.

**But each incident is its own Step Functions execution**, so multiple incidents run in parallel independently. One hanging approval doesn't block any other incident.

### Flow:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INCIDENT A (Execution 1)          INCIDENT B (Execution 2)            │
│                                                                         │
│  Initialize ─▶ Correlate           Initialize ─▶ Correlate             │
│  Score ─▶ RCA ─▶ Recommend         Score ─▶ RCA ─▶ Recommend           │
│       │                                  │                              │
│       ▼                                  ▼                              │
│  ┌──────────────────────┐          ┌──────────────────────┐            │
│  │ WaitForHumanApproval │          │ WaitForHumanApproval │            │
│  │                      │          │                      │            │
│  │ ⏸ PAUSED             │          │ ✓ APPROVED (2 min)   │            │
│  │ (no timeout)         │          └──────────┬───────────┘            │
│  │ UI: "Awaiting        │                     │                        │
│  │      Approval"       │                     ▼                        │
│  │                      │          Execute ─▶ Ticket ─▶ Notify ─▶ Done │
│  │ ...hangs until       │                                              │
│  │ human responds...    │          ← Incident B completes normally     │
│  │                      │                                              │
│  └──────────────────────┘                                              │
│  ← Incident A stays paused, no ticket/notify until approved            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Within a single incident execution:

```
InitializeIncident
       │
       ▼
CorrelateContext ──(fail)──▶ HandleCorrelationFailure
       │
       ▼
ScoreIncident ──(fail)──▶ HandleScoringFailure
       │
       ▼
CheckEscalation ──(sev≥4)──▶ SendEscalationAlert
       │
       ▼
AnalyzeRootCause ──(fail)──▶ HandleRCAFailure
       │
       ▼
RecommendRemediation ──(fail)──▶ HandleRemediationFailure
       │
       ▼
CheckAutoRemediation
       │
       ├── auto=true ──▶ ┌─────────────────────────────────────┐
       │                 │      WaitForHumanApproval            │
       │                 │      (.waitForTaskToken)             │
       │                 │                                     │
       │                 │  ⏸ WORKFLOW STOPS HERE               │
       │                 │  UI shows: "Awaiting Approval"       │
       │                 │  No ticket created yet               │
       │                 │  No notification sent yet            │
       │                 │  Hangs INDEFINITELY                  │
       │                 │                                     │
       │                 │  Human clicks Approve ──▶ continues  │
       │                 │  Human clicks Reject  ──▶ skips exec │
       │                 └─────────────────────────────────────┘
       │                          │
       │                          ▼
       │                 ExecuteRemediation (only if approved)
       │                          │
       ├── auto=false ────────────┘
       │
       ▼
CreateTicket ──(sev≥3)──▶ InvokeTicketCreation
       │
       ▼
NotifyTeam
       │
       ▼
DetermineWorkflowStatus ──▶ Resolved | Degraded
```

### Key behaviors:

1. **Sequential within each incident** — ticket and notify ONLY happen after approval
2. **Parallel across incidents** — each incident is a separate execution, they don't block each other
3. **Indefinite pause** — `.waitForTaskToken` has no timeout, hangs until callback
4. **Dashboard shows status** — "Awaiting Approval" with the proposed action visible in UI
5. **Approve/Reject via API** — human clicks button in dashboard, calls `SendTaskSuccess`/`SendTaskFailure`
6. **If no auto-remediation** — skips approval entirely, goes straight to ticket + notify

### Approval API:

```
POST /approve/{approval_id}
{
  "decision": "approved" | "rejected",
  "responder": "engineer@company.com"
}
```

This resumes the paused execution. Only then do ticket creation and notification proceed.

## Error Handling Strategy

Every Task state follows the same pattern:
1. **Retry** — automatic retries with backoff for transient failures
2. **Catch** — route to a failure handler (Pass or Task) that records the failure
3. **Continue** — workflow always progresses to the next step, never halts entirely

This ensures the workflow completes even when individual steps fail, producing a "degraded" result rather than a stuck execution.

## Input Schema

```json
{
  "signal": {
    "signal_id": "uuid",
    "service": "payment-api",
    "severity_score": 7,
    "detection_type": "metric",
    "timestamp": "2025-01-15T10:30:00Z",
    "auto_remediation_enabled": true,
    "source_event": { ... }
  }
}
```

## Output Schema

The final state produces an updated DynamoDB record with:
- `workflow_status`: "resolved" | "degraded"
- `status`: "mitigating" | "investigating"
- `completed_at`: ISO 8601 timestamp
