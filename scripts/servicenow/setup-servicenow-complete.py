"""
Complete ServiceNow Setup:
1. Create custom fields on change_request table
2. Create UI Actions (Approve/Reject buttons)
3. Sync all incident data to ServiceNow
"""
import boto3
import json
import base64
import urllib.request
import urllib.error

ssm = boto3.client('ssm', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Get ServiceNow credentials
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

print("=" * 70)
print("COMPLETE SERVICENOW SETUP FOR OUTAGESHIELD")
print("=" * 70)
print(f"Instance: {sn_instance}")

def sn_request(method, endpoint, data=None):
    """Make a ServiceNow API request"""
    url = f"https://{sn_instance}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/json')
    
    try:
        if data:
            response = urllib.request.urlopen(req, json.dumps(data).encode('utf-8'), timeout=30)
        else:
            response = urllib.request.urlopen(req, timeout=30)
        return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        print(f"   HTTP Error {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"   Error: {e}")
        return None

# ============================================================
# STEP 1: Create Custom Fields
# ============================================================
print("\n" + "=" * 70)
print("STEP 1: Creating Custom Fields on change_request table")
print("=" * 70)

fields = [
    {"name": "u_outageshield_incident_id", "label": "OutageShield Incident ID", "type": "string", "max_length": 50},
    {"name": "u_outageshield_service", "label": "Affected Service", "type": "string", "max_length": 100},
    {"name": "u_outageshield_severity", "label": "Severity Score", "type": "string", "max_length": 20},
    {"name": "u_outageshield_business_impact", "label": "Business Impact", "type": "string", "max_length": 20},
    {"name": "u_outageshield_affected_users", "label": "Affected Users", "type": "string", "max_length": 50},
    {"name": "u_outageshield_revenue_risk", "label": "Revenue at Risk", "type": "string", "max_length": 100},
    {"name": "u_outageshield_root_cause", "label": "Root Cause", "type": "string", "max_length": 4000},
    {"name": "u_outageshield_category", "label": "RCA Category", "type": "string", "max_length": 50},
    {"name": "u_outageshield_confidence", "label": "AI Confidence", "type": "string", "max_length": 20},
    {"name": "u_outageshield_investigation", "label": "Investigation Details", "type": "string", "max_length": 4000},
    {"name": "u_outageshield_ai_summary", "label": "AI Summary", "type": "string", "max_length": 4000},
    {"name": "u_outageshield_recommendations", "label": "Recommendations", "type": "string", "max_length": 4000},
    {"name": "u_outageshield_quick_actions", "label": "Quick Actions", "type": "string", "max_length": 4000},
    {"name": "u_outageshield_dashboard_url", "label": "Dashboard URL", "type": "url", "max_length": 500},
    {"name": "u_outageshield_callback_url", "label": "Callback URL", "type": "string", "max_length": 500},
    {"name": "u_outageshield_task_token", "label": "Task Token", "type": "string", "max_length": 2000},
    {"name": "u_outageshield_approval_status", "label": "Approval Status", "type": "string", "max_length": 50},
]

# Get sys_id for change_request table
result = sn_request('GET', '/api/now/table/sys_db_object?sysparm_query=name=change_request&sysparm_limit=1')
if result and result.get('result'):
    table_sys_id = result['result'][0]['sys_id']
    print(f"Found change_request table: {table_sys_id}")
    
    for field in fields:
        # Check if field exists
        check = sn_request('GET', f"/api/now/table/sys_dictionary?sysparm_query=name=change_request^element={field['name']}&sysparm_limit=1")
        if check and check.get('result'):
            print(f"   ✓ Field exists: {field['name']}")
        else:
            # Create field
            field_data = {
                "name": "change_request",
                "element": field['name'],
                "column_label": field['label'],
                "internal_type": field['type'],
                "max_length": field['max_length'],
                "active": True
            }
            create_result = sn_request('POST', '/api/now/table/sys_dictionary', field_data)
            if create_result:
                print(f"   ✓ Created field: {field['name']}")
            else:
                print(f"   ✗ Failed to create: {field['name']}")
else:
    print("   ✗ Could not find change_request table")

# ============================================================
# STEP 2: Create UI Actions (Approve/Reject Buttons)
# ============================================================
print("\n" + "=" * 70)
print("STEP 2: Creating UI Actions (Approve/Reject Buttons)")
print("=" * 70)

# Dashboard API callback URL
callback_url = "https://0gg0xhnc7i.execute-api.us-east-1.amazonaws.com/dev/approval/callback"

# Approve UI Action
approve_script = f'''
// OutageShield Approve Action
var incident_id = current.u_outageshield_incident_id;
var task_token = current.u_outageshield_task_token;

if (!incident_id || !task_token) {{
    gs.addErrorMessage('Missing OutageShield incident ID or task token');
}} else {{
    try {{
        var request = new sn_ws.RESTMessageV2();
        request.setEndpoint('{callback_url}');
        request.setHttpMethod('POST');
        request.setRequestHeader('Content-Type', 'application/json');
        
        var body = {{
            "incident_id": incident_id,
            "action": "approve",
            "task_token": task_token,
            "approved_by": gs.getUserName(),
            "change_number": current.number.toString()
        }};
        request.setRequestBody(JSON.stringify(body));
        
        var response = request.execute();
        var httpStatus = response.getStatusCode();
        
        if (httpStatus == 200) {{
            current.u_outageshield_approval_status = 'Approved';
            current.state = 'implement';  // Move to implement state
            current.update();
            gs.addInfoMessage('OutageShield remediation APPROVED. Workflow will continue.');
        }} else {{
            gs.addErrorMessage('Failed to send approval: HTTP ' + httpStatus);
        }}
    }} catch(e) {{
        gs.addErrorMessage('Error sending approval: ' + e.message);
    }}
}}
action.setRedirectURL(current);
'''

reject_script = f'''
// OutageShield Reject Action
var incident_id = current.u_outageshield_incident_id;
var task_token = current.u_outageshield_task_token;

if (!incident_id || !task_token) {{
    gs.addErrorMessage('Missing OutageShield incident ID or task token');
}} else {{
    var reason = '';
    // Prompt for rejection reason
    try {{
        var request = new sn_ws.RESTMessageV2();
        request.setEndpoint('{callback_url}');
        request.setHttpMethod('POST');
        request.setRequestHeader('Content-Type', 'application/json');
        
        var body = {{
            "incident_id": incident_id,
            "action": "reject",
            "task_token": task_token,
            "rejected_by": gs.getUserName(),
            "change_number": current.number.toString(),
            "reason": "Rejected via ServiceNow"
        }};
        request.setRequestBody(JSON.stringify(body));
        
        var response = request.execute();
        var httpStatus = response.getStatusCode();
        
        if (httpStatus == 200) {{
            current.u_outageshield_approval_status = 'Rejected';
            current.state = 'canceled';  // Cancel the change
            current.update();
            gs.addInfoMessage('OutageShield remediation REJECTED.');
        }} else {{
            gs.addErrorMessage('Failed to send rejection: HTTP ' + httpStatus);
        }}
    }} catch(e) {{
        gs.addErrorMessage('Error sending rejection: ' + e.message);
    }}
}}
action.setRedirectURL(current);
'''

ui_actions = [
    {
        "name": "OutageShield Approve",
        "table": "change_request",
        "action_name": "outageshield_approve",
        "script": approve_script,
        "form_button": True,
        "form_style": "btn-success",
        "hint": "Approve the AI-recommended remediation",
        "order": 100,
        "condition": "current.u_outageshield_incident_id != '' && current.u_outageshield_approval_status != 'Approved'"
    },
    {
        "name": "OutageShield Reject", 
        "table": "change_request",
        "action_name": "outageshield_reject",
        "script": reject_script,
        "form_button": True,
        "form_style": "btn-danger",
        "hint": "Reject the AI-recommended remediation",
        "order": 101,
        "condition": "current.u_outageshield_incident_id != '' && current.u_outageshield_approval_status != 'Rejected'"
    }
]

for action in ui_actions:
    # Check if exists
    check = sn_request('GET', f"/api/now/table/sys_ui_action?sysparm_query=name={action['name']}^table={action['table']}&sysparm_limit=1")
    
    action_data = {
        "name": action['name'],
        "table": action['table'],
        "action_name": action['action_name'],
        "script": action['script'],
        "form_button": action['form_button'],
        "form_style": action['form_style'],
        "hint": action['hint'],
        "order": action['order'],
        "condition": action['condition'],
        "active": True,
        "client": False,
        "form_link": False,
        "form_context_menu": False,
        "list_banner_button": False,
        "list_bottom_button": False,
        "list_context_menu": False,
        "list_link": False
    }
    
    if check and check.get('result'):
        # Update existing
        sys_id = check['result'][0]['sys_id']
        result = sn_request('PATCH', f"/api/now/table/sys_ui_action/{sys_id}", action_data)
        if result:
            print(f"   ✓ Updated: {action['name']}")
        else:
            print(f"   ✗ Failed to update: {action['name']}")
    else:
        # Create new
        result = sn_request('POST', '/api/now/table/sys_ui_action', action_data)
        if result:
            print(f"   ✓ Created: {action['name']}")
        else:
            print(f"   ✗ Failed to create: {action['name']}")

# ============================================================
# STEP 3: Sync All Incident Data to ServiceNow
# ============================================================
print("\n" + "=" * 70)
print("STEP 3: Syncing Incident Data to ServiceNow")
print("=" * 70)

incidents_table = dynamodb.Table('outageshield-incidents-dev')
ai_table = dynamodb.Table('outageshield-ai-reasoning-dev')
approvals_table = dynamodb.Table('outageshield-approvals-dev')

# Get all incidents with ServiceNow changes
result = incidents_table.scan()
synced = 0

for item in result.get('Items', []):
    sn_change = item.get('servicenow_change')
    if not sn_change:
        continue
    
    incident_id = item.get('incident_id')
    print(f"\nSyncing {incident_id} -> {sn_change}")
    
    # Get AI reasoning
    ai_data = {}
    try:
        ai_result = ai_table.query(
            KeyConditionExpression='incident_id = :iid',
            ExpressionAttributeValues={':iid': incident_id},
            Limit=1
        )
        if ai_result.get('Items'):
            ai_data = ai_result['Items'][0]
    except:
        pass
    
    # Get approval data (for task token)
    approval_data = {}
    try:
        approval_result = approvals_table.get_item(Key={'incident_id': incident_id})
        if approval_result.get('Item'):
            approval_data = approval_result['Item']
    except:
        pass
    
    # Build investigation text
    investigation_parts = []
    if item.get('agent_investigation'):
        investigation_parts.append("=== AGENT INVESTIGATION ===")
        investigation_parts.append(str(item.get('agent_investigation'))[:1500])
    if ai_data.get('investigation_summary'):
        investigation_parts.append("\n=== INVESTIGATION SUMMARY ===")
        investigation_parts.append(str(ai_data.get('investigation_summary')))
    if item.get('scoring_reasoning'):
        investigation_parts.append("\n=== BUSINESS IMPACT ANALYSIS ===")
        investigation_parts.append(str(item.get('scoring_reasoning')))
    investigation_text = "\n".join(investigation_parts)[:3900]
    
    # Build AI summary with quick actions
    ai_summary_parts = []
    if ai_data.get('ai_summary'):
        ai_summary_parts.append(str(ai_data.get('ai_summary')))
    ai_summary_text = "\n".join(ai_summary_parts)[:3900]
    
    # Build quick actions text
    quick_actions_text = ""
    if ai_data.get('quick_actions'):
        try:
            qa = ai_data.get('quick_actions')
            if isinstance(qa, str):
                qa = json.loads(qa)
            if qa:
                qa_lines = [f"=== QUICK ACTIONS ({len(qa)}) ==="]
                for i, action in enumerate(qa[:10], 1):
                    qa_lines.append(f"{i}. {action.get('label', '')}")
                    if action.get('command'):
                        qa_lines.append(f"   Command: {action.get('command')[:100]}")
                quick_actions_text = "\n".join(qa_lines)[:3900]
        except:
            pass
    
    # Build recommendations text
    recommendations_text = ""
    if ai_data.get('recommended_action'):
        rec = ai_data.get('recommended_action')
        if isinstance(rec, dict):
            recommendations_text = f"""=== RECOMMENDED ACTION ===
Type: {rec.get('type', 'N/A')}
Description: {rec.get('description', 'N/A')}
Confidence: {rec.get('confidence', 'N/A')}%
Risk: {rec.get('risk', 'N/A')}
Estimated TTR: {rec.get('estimated_ttr_minutes', 'N/A')} minutes
Reasoning: {rec.get('reasoning', 'N/A')[:500]}"""
    
    # Get root cause info
    root_cause = str(item.get('root_cause', ''))[:3900]
    rca_category = ''
    confidence = ''
    if item.get('root_causes'):
        try:
            rcs = item.get('root_causes')
            if isinstance(rcs, str):
                rcs = json.loads(rcs)
            if rcs and len(rcs) > 0:
                rca_category = rcs[0].get('category', '')
                confidence = f"{rcs[0].get('confidence', '')}%"
        except:
            pass
    
    # Find the change request sys_id
    check = sn_request('GET', f"/api/now/table/change_request?sysparm_query=number={sn_change}&sysparm_limit=1")
    if not check or not check.get('result'):
        print(f"   ✗ Change request not found: {sn_change}")
        continue
    
    sys_id = check['result'][0]['sys_id']
    
    # Update the change request with all data
    update_data = {
        "u_outageshield_incident_id": incident_id,
        "u_outageshield_service": item.get('service', ''),
        "u_outageshield_severity": f"{item.get('severity_score', 'N/A')}/5",
        "u_outageshield_business_impact": f"{item.get('business_impact_score', 'N/A')}/10",
        "u_outageshield_affected_users": str(item.get('affected_users', '')),
        "u_outageshield_revenue_risk": str(item.get('revenue_at_risk', '')),
        "u_outageshield_root_cause": root_cause,
        "u_outageshield_category": rca_category,
        "u_outageshield_confidence": confidence,
        "u_outageshield_investigation": investigation_text,
        "u_outageshield_ai_summary": ai_summary_text,
        "u_outageshield_recommendations": recommendations_text,
        "u_outageshield_quick_actions": quick_actions_text,
        "u_outageshield_dashboard_url": f"https://d2k1km1tzlio49.cloudfront.net/incidents/{incident_id}",
        "u_outageshield_callback_url": callback_url,
        "u_outageshield_task_token": approval_data.get('task_token', ''),
        "short_description": f"[OutageShield] {item.get('service', 'Unknown')} - {incident_id}",
        "description": f"""OutageShield AI Incident Analysis

Incident ID: {incident_id}
Service: {item.get('service', 'Unknown')}
Severity: {item.get('severity_score', 'N/A')}/5
Business Impact: {item.get('business_impact_score', 'N/A')}/10
Status: {item.get('status', 'Unknown')}

Root Cause: {root_cause[:500]}

Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/{incident_id}
"""
    }
    
    result = sn_request('PATCH', f"/api/now/table/change_request/{sys_id}", update_data)
    if result:
        print(f"   ✓ Synced successfully")
        synced += 1
    else:
        print(f"   ✗ Failed to sync")

print("\n" + "=" * 70)
print(f"COMPLETE! Synced {synced} incidents to ServiceNow")
print("=" * 70)
print("\nServiceNow changes now have:")
print("  - All incident data in custom fields")
print("  - Approve/Reject buttons on the form")
print("  - Callback URL for workflow integration")
print("\nTo test, open a change request in ServiceNow and click Approve or Reject")
