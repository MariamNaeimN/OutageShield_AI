"""
Update Approval Lambda to store ServiceNow URL in DynamoDB
"""

import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')

FUNCTION_NAME = 'outageshield-approval-dev'

# Get ServiceNow instance for URL
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']

lambda_code = f'''
import json
import boto3
import os
import uuid
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
ssm = boto3.client('ssm')

APPROVALS_TABLE = os.environ.get('APPROVALS_TABLE', 'outageshield-approvals-dev')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
APPROVAL_TOPIC_ARN = os.environ.get('APPROVAL_TOPIC_ARN', '')
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://d2k1km1tzlio49.cloudfront.net')
SN_INSTANCE = '{sn_instance}'


def get_sn_credentials():
    """Get ServiceNow credentials from SSM"""
    try:
        username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
        password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
        return username, password
    except:
        return None, None


def create_servicenow_change(incident_id, service, severity, proposed_action, task_token, event_data=None):
    """Create a change request in ServiceNow and return the change number"""
    username, password = get_sn_credentials()
    if not username:
        print("ServiceNow credentials not found")
        return None, None
    
    credentials = base64.b64encode(f"{{username}}:{{password}}".encode()).decode()
    
    # Extract all data from event
    event_data = event_data or {{}}
    
    # Build description
    action_desc = ''
    if isinstance(proposed_action, dict):
        action_desc = proposed_action.get('description', str(proposed_action))
    else:
        action_desc = str(proposed_action)
    
    # Get additional data
    root_cause = event_data.get('root_cause', '')
    if isinstance(root_cause, dict):
        root_cause = root_cause.get('description', str(root_cause))
    
    investigation = event_data.get('investigation', '')
    ai_summary = event_data.get('ai_summary', '')
    postmortem = event_data.get('postmortem', '')
    affected_users = event_data.get('affected_users', '')
    revenue_risk = event_data.get('revenue_risk', '')
    business_impact = event_data.get('business_impact', '')
    confidence = event_data.get('confidence', '')
    rca_category = event_data.get('rca_category', '')
    recommendations = event_data.get('recommendations', '')
    quick_actions = event_data.get('quick_actions', '')
    remediation = event_data.get('remediation', '')
    
    # Map severity to priority and risk
    priority_map = {{5: '1', 4: '2', 3: '3', 2: '4', 1: '4'}}
    risk_map = {{5: 'high', 4: 'high', 3: 'moderate', 2: 'low', 1: 'low'}}
    impact_map = {{5: '1', 4: '1', 3: '2', 2: '3', 1: '3'}}
    
    change_data = {{
        # Standard ServiceNow fields
        "short_description": f"[OutageShield] {{incident_id}} - {{service}} - Severity {{severity}}/5",
        "description": f"OutageShield AI Incident\\n\\nIncident ID: {{incident_id}}\\nService: {{service}}\\nSeverity: {{severity}}/5\\n\\nRoot Cause:\\n{{root_cause}}\\n\\nProposed Action:\\n{{action_desc}}",
        "type": "emergency",
        "category": "Software",
        "priority": priority_map.get(severity, '3'),
        "risk": risk_map.get(severity, 'moderate'),
        "impact": impact_map.get(severity, '2'),
        "state": "-5",  # New
        "approval": "requested",
        
        # OutageShield custom fields
        "u_outageshield_incident_id": incident_id,
        "u_outageshield_service": service,
        "u_outageshield_severity": str(severity),
        "u_outageshield_root_cause": str(root_cause)[:4000] if root_cause else "",
        "u_outageshield_recommendation": action_desc[:4000] if action_desc else "",
        "u_outageshield_investigation": str(investigation)[:4000] if investigation else "",
        "u_outageshield_ai_summary": str(ai_summary)[:4000] if ai_summary else "",
        "u_outageshield_postmortem": str(postmortem)[:4000] if postmortem else "",
        "u_outageshield_affected_users": str(affected_users) if affected_users else "",
        "u_outageshield_revenue_risk": str(revenue_risk) if revenue_risk else "",
        "u_outageshield_business_impact": str(business_impact) if business_impact else "",
        "u_outageshield_confidence": str(confidence) if confidence else "",
        "u_outageshield_rca_category": str(rca_category) if rca_category else "",
        "u_outageshield_remediation": str(remediation)[:4000] if remediation else "",
        "u_outageshield_recommendations": str(recommendations)[:4000] if recommendations else "",
        "u_outageshield_quick_actions": str(quick_actions)[:4000] if quick_actions else "",
        "u_outageshield_task_token": task_token[:200] if task_token else "",
        "u_outageshield_callback_url": f"https://0h9xnvnqf5.execute-api.us-east-1.amazonaws.com/dev/approval/callback",
        "u_outageshield_dashboard_url": f"{{DASHBOARD_URL}}/incidents/{{incident_id}}"
    }}
    
    url = f"https://{{SN_INSTANCE}}/api/now/table/change_request"
    data = json.dumps(change_data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'Basic {{credentials}}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            change_number = result['result']['number']
            sys_id = result['result']['sys_id']
            print(f"Created ServiceNow change: {{change_number}}")
            return change_number, sys_id
    except Exception as e:
        print(f"Failed to create ServiceNow change: {{e}}")
        return None, None


def lambda_handler(event, context):
    print(f"Received event: {{json.dumps(event, default=str)}}")
    
    if 'httpMethod' in event or 'requestContext' in event:
        return handle_api_gateway_request(event)
    
    if 'task_token' in event:
        return handle_send_approval(event)
    
    mode = event.get('mode', '')
    if mode == 'respond':
        return handle_approval_response(event)
    
    return {{
        'statusCode': 400,
        'headers': cors_headers(),
        'body': json.dumps({{'error': 'Unknown invocation mode'}})
    }}


def cors_headers():
    return {{
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }}
'''

lambda_code += f'''

def handle_api_gateway_request(event):
    if event.get('httpMethod') == 'OPTIONS':
        return {{'statusCode': 200, 'headers': cors_headers(), 'body': ''}}
    
    path = event.get('path', '') or event.get('rawPath', '')
    path_params = event.get('pathParameters', {{}}) or {{}}
    approval_id = path_params.get('approvalId') or path_params.get('approval_id')
    
    if not approval_id:
        parts = path.split('/')
        if 'approve' in parts:
            idx = parts.index('approve')
            if idx + 1 < len(parts):
                approval_id = parts[idx + 1]
    
    if not approval_id:
        return {{'statusCode': 400, 'headers': cors_headers(), 'body': json.dumps({{'error': 'Missing approval_id'}})}}
    
    body = event.get('body', '{{}}')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {{}}
    
    decision = body.get('decision', 'approved')
    responder = body.get('responder', 'dashboard-user')
    
    return handle_approval_response({{'approval_id': approval_id, 'decision': decision, 'responder': responder}})


def handle_send_approval(event):
    """Store task token, create ServiceNow change, and send approval request."""
    task_token = event['task_token']
    incident_id = event['incident_id']
    service = event.get('service', 'unknown')
    severity_score = event.get('severity_score', 3)
    proposed_action = event.get('proposed_action', {{}})
    risk_level = event.get('risk_level', 'medium')
    workflow_id = event.get('workflow_id', '')

    approval_id = incident_id
    
    # Fetch full incident data from DynamoDB for ServiceNow fields
    event_data = {{}}
    try:
        incidents_table = dynamodb.Table(INCIDENTS_TABLE)
        resp = incidents_table.get_item(Key={{'incident_id': incident_id}})
        item = resp.get('Item', {{}})
        
        # Extract all relevant data
        event_data['root_cause'] = item.get('root_cause', '')
        event_data['investigation'] = item.get('agent_investigation', item.get('investigation', ''))
        event_data['affected_users'] = item.get('affected_users', '')
        event_data['revenue_risk'] = item.get('revenue_at_risk', item.get('revenue_risk', ''))
        event_data['business_impact'] = item.get('business_impact', item.get('business_impact_score', ''))
        event_data['confidence'] = item.get('confidence', '')
        event_data['rca_category'] = item.get('rca_category', '')
        event_data['remediation'] = item.get('remediation', '')
        
        # Parse recommendations
        recs_raw = item.get('recommendations_raw', '')
        if recs_raw:
            try:
                recs = json.loads(recs_raw) if isinstance(recs_raw, str) else recs_raw
                event_data['recommendations'] = json.dumps(recs, indent=2)
            except:
                event_data['recommendations'] = str(recs_raw)
        
        # Parse summary for AI summary and quick actions
        summary_raw = item.get('remediation_summary', '')
        if summary_raw:
            try:
                summary = json.loads(summary_raw) if isinstance(summary_raw, str) else summary_raw
                event_data['ai_summary'] = summary.get('ai_summary', '')
                event_data['quick_actions'] = json.dumps(summary.get('quick_actions', []), indent=2)
            except:
                event_data['ai_summary'] = str(summary_raw)[:500]
        
        # Get postmortem
        event_data['postmortem'] = item.get('postmortem', '')
        
        print(f"Fetched incident data for {{incident_id}}")
    except Exception as e:
        print(f"Failed to fetch incident data: {{e}}")
    
    # Create ServiceNow change request with all data
    change_number, sys_id = create_servicenow_change(
        incident_id, service, severity_score, proposed_action, task_token, event_data
    )
    
    # Build ServiceNow URL - use standard change_request form
    servicenow_url = None
    if change_number:
        servicenow_url = f"https://{{SN_INSTANCE}}/change_request.do?sysparm_query=number={{change_number}}"

    # Store token in DynamoDB
    table = dynamodb.Table(APPROVALS_TABLE)
    table.put_item(Item={{
        'approval_id': approval_id,
        'incident_id': incident_id,
        'task_token': task_token,
        'service': service,
        'severity_score': severity_score,
        'proposed_action': json.dumps(proposed_action) if isinstance(proposed_action, dict) else str(proposed_action),
        'risk_level': str(risk_level) if risk_level else 'medium',
        'workflow_id': workflow_id,
        'servicenow_change': change_number or '',
        'servicenow_url': servicenow_url or '',
        'status': 'pending',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'ttl': int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
    }})
    print(f"Stored task token for incident {{incident_id}}")

    # Update incident status with ServiceNow URL
    try:
        incidents_table = dynamodb.Table(INCIDENTS_TABLE)
        update_expr = 'SET #s = :status, awaiting_approval_since = :ts'
        expr_values = {{
            ':status': 'Awaiting Approval',
            ':ts': datetime.now(timezone.utc).isoformat()
        }}
        
        if change_number:
            update_expr += ', servicenow_change = :sn_change, servicenow_url = :sn_url'
            expr_values[':sn_change'] = change_number
            expr_values[':sn_url'] = servicenow_url
        
        incidents_table.update_item(
            Key={{'incident_id': incident_id}},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={{'#s': 'status'}},
            ExpressionAttributeValues=expr_values
        )
        print(f"Updated incident {{incident_id}} with ServiceNow change {{change_number}}")
    except Exception as e:
        print(f"Failed to update incident status: {{e}}")

    # Send approval notification
    approve_url = f"{{DASHBOARD_URL}}/incidents/{{incident_id}}"
    
    action_desc = ''
    if isinstance(proposed_action, dict):
        action_desc = proposed_action.get('description', str(proposed_action))
    else:
        action_desc = str(proposed_action)

    message = f"""🔔 REMEDIATION APPROVAL REQUIRED

Incident: {{incident_id}}
Service: {{service}}
Severity: {{severity_score}}/5
Risk Level: {{risk_level}}

Proposed Action:
{{action_desc}}

👉 Approve in Dashboard:
{{approve_url}}

👉 Approve in ServiceNow:
{{servicenow_url or 'N/A'}}

This workflow is PAUSED until you approve or reject."""

    if APPROVAL_TOPIC_ARN:
        try:
            sns.publish(
                TopicArn=APPROVAL_TOPIC_ARN,
                Subject=f"[APPROVAL NEEDED] {{service}} - {{incident_id}}",
                Message=message
            )
        except Exception as e:
            print(f"Failed to send SNS notification: {{e}}")

    print(f"Approval request created. ServiceNow: {{change_number}}")
'''

lambda_code += '''

def handle_approval_response(event):
    """Human responded via Dashboard/API Gateway. Resume Step Functions."""
    approval_id = event.get('approval_id')
    decision = event.get('decision', 'approved')
    responder = event.get('responder', 'unknown')

    if not approval_id:
        return {'statusCode': 400, 'headers': cors_headers(), 'body': json.dumps({'error': 'Missing approval_id'})}

    table = dynamodb.Table(APPROVALS_TABLE)
    
    try:
        response = table.get_item(Key={'approval_id': approval_id})
        item = response.get('Item')
    except Exception as e:
        return {'statusCode': 500, 'headers': cors_headers(), 'body': json.dumps({'error': f'Database error: {str(e)}'})}

    if not item:
        return {'statusCode': 404, 'headers': cors_headers(), 'body': json.dumps({'error': f'Approval request {approval_id} not found'})}

    if item.get('status') != 'pending':
        return {'statusCode': 409, 'headers': cors_headers(), 'body': json.dumps({'error': 'Approval already processed', 'status': item.get('status')})}

    task_token = item.get('task_token')
    incident_id = item.get('incident_id', approval_id)
    servicenow_change = item.get('servicenow_change', '')

    if not task_token:
        return {'statusCode': 400, 'headers': cors_headers(), 'body': json.dumps({'error': 'No task token found'})}

    # Update approval record
    table.update_item(
        Key={'approval_id': approval_id},
        UpdateExpression='SET #s = :status, responded_at = :ts, responder = :resp, decision = :dec',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':status': decision,
            ':ts': datetime.now(timezone.utc).isoformat(),
            ':resp': responder,
            ':dec': decision
        }
    )

    # Update incident status
    try:
        incidents_table = dynamodb.Table(INCIDENTS_TABLE)
        new_status = 'Mitigating' if decision == 'approved' else 'Investigating'
        incidents_table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET #s = :status, approval_decision = :dec, approved_by = :by, approved_at = :ts',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':dec': decision,
                ':by': responder,
                ':ts': datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        print(f"Failed to update incident status: {e}")

    # Resume Step Functions
    try:
        if decision == 'approved':
            sfn.send_task_success(
                taskToken=task_token,
                output=json.dumps({
                    'decision': 'approved',
                    'responder': responder,
                    'responded_at': datetime.now(timezone.utc).isoformat(),
                    'servicenow_change': servicenow_change
                })
            )
        else:
            sfn.send_task_failure(
                taskToken=task_token,
                error='ApprovalRejected',
                cause=f'Rejected by {responder}'
            )
    except Exception as e:
        return {'statusCode': 500, 'headers': cors_headers(), 'body': json.dumps({'error': f'Failed to resume workflow: {str(e)}'})}

    return {
        'statusCode': 200,
        'headers': cors_headers(),
        'body': json.dumps({
            'success': True,
            'approvalId': approval_id,
            'decision': decision,
            'responder': responder,
            'servicenow_change': servicenow_change
        })
    }
'''

# Create deployment package
import zipfile
import io

print("=" * 60)
print("UPDATING APPROVAL LAMBDA WITH SERVICENOW URL")
print("=" * 60)

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', lambda_code)
zip_buffer.seek(0)

try:
    response = lambda_client.update_function_code(
        FunctionName=FUNCTION_NAME,
        ZipFile=zip_buffer.read()
    )
    print(f"✅ Updated Lambda code: {FUNCTION_NAME}")
    
    # Wait for update
    import time
    time.sleep(3)
    
    # Update environment
    lambda_client.update_function_configuration(
        FunctionName=FUNCTION_NAME,
        Environment={
            'Variables': {
                'APPROVALS_TABLE': 'outageshield-approvals-dev',
                'INCIDENTS_TABLE': 'outageshield-incidents-dev',
                'APPROVAL_TOPIC_ARN': 'arn:aws:sns:us-east-1:471112982085:outageshield-alerts-dev',
                'DASHBOARD_URL': 'https://d2k1km1tzlio49.cloudfront.net',
                'ENVIRONMENT': 'dev'
            }
        },
        Timeout=60,
        MemorySize=256
    )
    print("✅ Updated environment variables")
    
except Exception as e:
    print(f"❌ Error: {e}")

print(f"""
✅ Approval Lambda updated!

Now stores in DynamoDB:
- servicenow_change: CHG number
- servicenow_url: https://{sn_instance}/outageshield_incident.do?number=CHGxxxxx

Dashboard will show ServiceNow link in incident details.
""")
