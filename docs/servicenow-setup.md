# Human Approval Setup Guide

OutageShield AI supports human-in-the-loop approval for remediation actions. This guide covers both the **Dashboard-based approval** (default) and optional **ServiceNow integration**.

---

## Dashboard-Based Approval (Default)

The human approval flow is now fully integrated into the OutageShield dashboard:

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    INCIDENT WORKFLOW                             │
├─────────────────────────────────────────────────────────────────┤
│  1. Detection → 2. Correlation → 3. Scoring → 4. RCA            │
│  5. Agent Investigation → 6. Remediation → 7. Summary           │
│                           ↓                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  8. HUMAN APPROVAL GATE (waitForTaskToken)              │    │
│  │     • Workflow PAUSES here                              │    │
│  │     • Incident status: "Awaiting Approval"              │    │
│  │     • Dashboard shows Approve/Reject buttons            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           ↓                                      │
│  9. Execute Remediation → 10. Create Ticket → 11. Notify        │
│  12. Generate Postmortem → 13. Done                             │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| `outageshield-approval-dev` Lambda | Stores task token, updates incident to "Awaiting Approval" |
| `outageshield-approvals-dev` DynamoDB | Stores task tokens for pending approvals |
| Dashboard API `/approve/{id}` | Handles approve/reject from UI |
| Step Functions `waitForTaskToken` | Pauses workflow until approval |

### Using the Dashboard

1. When an incident reaches the approval stage, it shows **"Awaiting Approval"** status
2. Open the incident detail page
3. You'll see a purple **"Human Approval Required"** section
4. Review the AI recommendations
5. Click **"Approve Remediation"** or **"Reject"**
6. The workflow automatically resumes

### API Endpoint

```bash
# Approve
curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/approve/INC-XXXXX \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "responder": "your-name"}'

# Reject
curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/approve/INC-XXXXX \
  -H "Content-Type: application/json" \
  -d '{"decision": "rejected", "responder": "your-name"}'
```

---

## ServiceNow Integration (Optional)

If you want to use ServiceNow for approvals instead of the dashboard, follow the steps below.

---

## Step 1: Create Custom Fields on Change Request Table

Go to **ServiceNow Studio** → **Create Application File** → **Data Model** → **Dictionary Entry**

Create these fields on the `change_request` table:

| Field Label | Column Name | Type | Max Length |
|-------------|-------------|------|------------|
| OutageShield Incident ID | `u_outageshield_incident_id` | String | 50 |
| OutageShield Task Token | `u_outageshield_task_token` | String | 4000 |
| OutageShield Callback URL | `u_outageshield_callback_url` | String | 500 |
| OutageShield Severity | `u_outageshield_severity` | Integer | - |
| OutageShield Root Cause | `u_outageshield_root_cause` | String | 1000 |
| OutageShield Recommendation | `u_outageshield_recommendation` | String | 2000 |
| OutageShield Service | `u_outageshield_service` | String | 100 |

---

## Step 2: Create Business Rule (Callback on Approval)

Go to **ServiceNow Studio** → **Create Application File** → **Server Development** → **Business Rule**

**Settings:**
- **Name**: `OutageShield Approval Callback`
- **Table**: `change_request`
- **Active**: ✅ Checked
- **When**: `after`
- **Update**: ✅ Checked
- **Advanced**: ✅ Checked

**Script:**
```javascript
(function executeRule(current, previous /*null when async*/) {
    
    // Only process if callback URL exists (OutageShield change request)
    var callback_url = current.getValue('u_outageshield_callback_url');
    if (!callback_url || callback_url == '') {
        return;
    }
    
    // Only trigger when approval or state changes
    if (!current.approval.changes() && !current.state.changes()) {
        return;
    }
    
    var incident_id = current.getValue('u_outageshield_incident_id');
    var task_token = current.getValue('u_outageshield_task_token');
    
    // Determine approval decision
    var decision = 'rejected';
    var approval_value = current.getValue('approval');
    var state_value = current.getValue('state');
    
    if (approval_value == 'approved' || 
        state_value == 'implement' || 
        state_value == 'scheduled' ||
        state_value == 'review') {
        decision = 'approved';
    }
    
    // Get approver info
    var approver = gs.getUserDisplayName();
    if (current.closed_by && current.closed_by.getDisplayValue()) {
        approver = current.closed_by.getDisplayValue();
    }
    
    // Build callback payload
    var payload = {
        incident_id: incident_id,
        task_token: task_token,
        decision: decision,
        approver: approver,
        approved_at: new GlideDateTime().toString(),
        comments: current.getValue('close_notes') || '',
        change_number: current.getValue('number'),
        sys_id: current.getUniqueValue()
    };
    
    // Send callback to OutageShield AWS
    try {
        var restMessage = new sn_ws.RESTMessageV2();
        restMessage.setEndpoint(callback_url);
        restMessage.setHttpMethod('POST');
        restMessage.setRequestHeader('Content-Type', 'application/json');
        restMessage.setRequestBody(JSON.stringify(payload));
        restMessage.setHttpTimeout(30000);
        
        var response = restMessage.execute();
        var httpStatus = response.getStatusCode();
        
        gs.info('OutageShield callback sent: ' + incident_id + 
                ', decision: ' + decision + ', status: ' + httpStatus);
        
        current.work_notes = '[OutageShield] Callback sent.\nDecision: ' + 
                            decision.toUpperCase() + '\nStatus: ' + httpStatus;
        
    } catch (ex) {
        gs.error('OutageShield callback failed: ' + ex.getMessage());
        current.work_notes = '[OutageShield] Callback FAILED: ' + ex.getMessage();
    }
    
})(current, previous);
```

---

## Step 3: Create Scripted REST API

Go to **ServiceNow Studio** → **Create Application File** → **Service Development** → **Scripted REST API**

**API Settings:**
- **Name**: `OutageShield API`
- **API ID**: `outageshield`

Then create a **Resource**:
- **Name**: `Create Change Request`
- **HTTP Method**: `POST`
- **Relative path**: `/change_request`

**Script:**
```javascript
(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    
    var body = request.body.data;
    
    // Validate required fields
    if (!body.incident_id || !body.task_token || !body.callback_url) {
        response.setStatus(400);
        return {
            success: false,
            error: 'Missing required fields: incident_id, task_token, callback_url'
        };
    }
    
    // Create Change Request
    var gr = new GlideRecord('change_request');
    gr.initialize();
    
    // Standard fields
    gr.short_description = '[OutageShield] ' + body.incident_id + ' - ' + (body.service || 'Unknown Service');
    gr.description = buildDescription(body);
    gr.category = 'Software';
    gr.type = 'Standard';
    
    // Priority based on severity
    var severity = parseInt(body.severity) || 3;
    if (severity >= 4) {
        gr.priority = '2';
        gr.risk = 'High';
    } else if (severity >= 3) {
        gr.priority = '3';
        gr.risk = 'Moderate';
    } else {
        gr.priority = '4';
        gr.risk = 'Low';
    }
    
    // OutageShield custom fields
    gr.u_outageshield_incident_id = body.incident_id;
    gr.u_outageshield_task_token = body.task_token;
    gr.u_outageshield_callback_url = body.callback_url;
    gr.u_outageshield_severity = severity;
    gr.u_outageshield_root_cause = body.root_cause || '';
    gr.u_outageshield_recommendation = body.recommendation || '';
    gr.u_outageshield_service = body.service || '';
    
    // Set state for approval workflow
    gr.state = '-5';
    gr.approval = 'requested';
    
    var sys_id = gr.insert();
    
    if (sys_id) {
        gr.get(sys_id);
        var change_number = gr.getValue('number');
        
        gs.info('OutageShield: Created change request ' + change_number + 
                ' for incident ' + body.incident_id);
        
        response.setStatus(201);
        return {
            success: true,
            sys_id: sys_id,
            number: change_number,
            incident_id: body.incident_id,
            message: 'Change request created successfully'
        };
    } else {
        response.setStatus(500);
        return {
            success: false,
            error: 'Failed to create change request'
        };
    }
    
    function buildDescription(data) {
        var desc = '=== OUTAGESHIELD AI INCIDENT ===\n\n';
        
        desc += 'INCIDENT DETAILS\n';
        desc += '----------------\n';
        desc += 'Incident ID: ' + (data.incident_id || 'N/A') + '\n';
        desc += 'Service: ' + (data.service || 'N/A') + '\n';
        desc += 'Alarm: ' + (data.alarm_name || 'N/A') + '\n';
        desc += 'Severity: ' + (data.severity || 'N/A') + '/5\n\n';
        
        desc += 'IMPACT ANALYSIS\n';
        desc += '---------------\n';
        desc += 'Affected Users: ' + (data.affected_users || 'N/A') + '\n';
        desc += 'Revenue at Risk: ' + (data.revenue_at_risk || 'N/A') + '\n\n';
        
        desc += 'ROOT CAUSE ANALYSIS\n';
        desc += '-------------------\n';
        desc += 'Root Cause: ' + (data.root_cause || 'N/A') + '\n';
        desc += 'Category: ' + (data.rca_category || 'N/A') + '\n';
        desc += 'Confidence: ' + (data.confidence || 'N/A') + '%\n\n';
        
        desc += 'RECOMMENDED ACTION\n';
        desc += '------------------\n';
        desc += (data.recommendation || 'N/A') + '\n\n';
        
        if (data.ai_summary) {
            desc += 'AI SUMMARY\n';
            desc += '----------\n';
            desc += data.ai_summary + '\n\n';
        }
        
        desc += 'DASHBOARD LINK\n';
        desc += '--------------\n';
        desc += 'https://d2k1km1tzlio49.cloudfront.net/incidents/' + data.incident_id + '\n';
        
        return desc;
    }
    
})(request, response);
```

---

## Step 4: Create UI Actions (Approve/Reject Buttons)

Go to **ServiceNow Studio** → **Create Application File** → **Forms & UI** → **UI Action**

### Approve Button:
- **Name**: `OutageShield Approve`
- **Table**: `change_request`
- **Action name**: `outageshield_approve`
- **Show update**: ✅
- **Form button**: ✅
- **Condition**: `current.u_outageshield_incident_id != ''`

**Script:**
```javascript
current.approval = 'approved';
current.state = 'implement';
current.work_notes = '[OutageShield] Remediation APPROVED by ' + gs.getUserDisplayName();
current.update();
action.setRedirectURL(current);
```

### Reject Button:
- **Name**: `OutageShield Reject`
- **Table**: `change_request`
- **Action name**: `outageshield_reject`
- **Show update**: ✅
- **Form button**: ✅
- **Condition**: `current.u_outageshield_incident_id != ''`

**Script:**
```javascript
current.approval = 'rejected';
current.state = 'canceled';
current.work_notes = '[OutageShield] Remediation REJECTED by ' + gs.getUserDisplayName();
current.update();
action.setRedirectURL(current);
```

---

## Step 5: Test the Integration

### Test URL:
```
POST https://dev252089.service-now.com/api/x_YOUR_SCOPE/outageshield/change_request
```

### Test Payload:
```json
{
    "incident_id": "INC-TEST001",
    "service": "payment-service",
    "alarm_name": "HighCPU-payment-service",
    "severity": 4,
    "affected_users": 500000,
    "revenue_at_risk": "$15,000/hour",
    "root_cause": "Database connection pool exhaustion",
    "rca_category": "capacity",
    "confidence": 90,
    "recommendation": "Scale the service to handle increased load",
    "ai_summary": "The payment-service experienced high CPU due to connection pool exhaustion.",
    "task_token": "TEST_TOKEN_12345",
    "callback_url": "https://your-api-gateway.amazonaws.com/dev/approval/callback"
}
```

### Headers:
```
Content-Type: application/json
Authorization: Basic <base64_encoded_credentials>
```

---

## Summary of Components

| # | Type | Name | Purpose |
|---|------|------|---------|
| 1 | Dictionary Entries | 7 custom fields | Store OutageShield data on change_request |
| 2 | Business Rule | OutageShield Approval Callback | Send callback to AWS on approval |
| 3 | Scripted REST API | OutageShield API | Receive change requests from AWS |
| 4 | UI Action | OutageShield Approve | Approve button on form |
| 5 | UI Action | OutageShield Reject | Reject button on form |

---

## Next Steps

After setting up ServiceNow, you need to:
1. Create the AWS Lambda to send change requests to ServiceNow
2. Create the AWS Lambda to receive callbacks from ServiceNow
3. Update Step Functions to use `waitForTaskToken` pattern

See `docs/aws-approval-setup.md` for AWS-side implementation.
