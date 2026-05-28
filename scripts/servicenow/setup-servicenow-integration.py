"""
Setup ServiceNow Integration for OutageShield AI

Your ServiceNow PDI: dev252089.service-now.com

This script:
1. Stores ServiceNow credentials in AWS SSM Parameter Store
2. Creates Lambda to send change requests to ServiceNow
3. Updates the approval Lambda to also create ServiceNow change requests
"""

import boto3
import json
import getpass

ssm = boto3.client('ssm', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

SERVICENOW_INSTANCE = 'dev252089.service-now.com'

print("=" * 60)
print("SERVICENOW INTEGRATION SETUP")
print("=" * 60)
print(f"\nServiceNow Instance: {SERVICENOW_INSTANCE}")

# Step 1: Get ServiceNow credentials
print("\n1. ServiceNow Credentials")
print("   Enter your ServiceNow admin credentials:")
username = input("   Username (e.g., admin): ").strip()
password = getpass.getpass("   Password: ")

if not username or not password:
    print("   ❌ Username and password are required")
    exit(1)

# Step 2: Store credentials in SSM Parameter Store
print("\n2. Storing credentials in AWS SSM Parameter Store...")
try:
    ssm.put_parameter(
        Name='/outageshield/servicenow/instance',
        Value=SERVICENOW_INSTANCE,
        Type='String',
        Overwrite=True,
        Description='ServiceNow instance URL'
    )
    print(f"   ✅ Stored /outageshield/servicenow/instance")
    
    ssm.put_parameter(
        Name='/outageshield/servicenow/username',
        Value=username,
        Type='SecureString',
        Overwrite=True,
        Description='ServiceNow username'
    )
    print(f"   ✅ Stored /outageshield/servicenow/username")
    
    ssm.put_parameter(
        Name='/outageshield/servicenow/password',
        Value=password,
        Type='SecureString',
        Overwrite=True,
        Description='ServiceNow password'
    )
    print(f"   ✅ Stored /outageshield/servicenow/password")
except Exception as e:
    print(f"   ❌ Failed to store credentials: {e}")
    exit(1)

# Step 3: Update approval Lambda to include ServiceNow integration
print("\n3. Updating approval Lambda with ServiceNow integration...")

approval_lambda_code = '''
import json
import boto3
import os
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
ssm = boto3.client('ssm')

APPROVALS_TABLE = os.environ.get('APPROVALS_TABLE', 'outageshield-approvals-dev')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
APPROVAL_TOPIC_ARN = os.environ.get('APPROVAL_TOPIC_ARN', '')
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://d2k1km1tzlio49.cloudfront.net')
SERVICENOW_ENABLED = os.environ.get('SERVICENOW_ENABLED', 'true').lower() == 'true'


def get_servicenow_config():
    """Get ServiceNow configuration from SSM"""
    try:
        instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
        username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
        password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
        return instance, username, password
    except Exception as e:
        print(f"Failed to get ServiceNow config: {e}")
        return None, None, None


def create_servicenow_change_request(incident_data):
    """Create a change request in ServiceNow"""
    instance, username, password = get_servicenow_config()
    if not instance:
        print("ServiceNow not configured, skipping")
        return None
    
    url = f"https://{instance}/api/now/table/change_request"
    
    # Build change request payload
    payload = {
        "short_description": f"[OutageShield] {incident_data.get('incident_id')} - {incident_data.get('service')}",
        "description": build_description(incident_data),
        "category": "Software",
        "type": "Standard",
        "priority": get_priority(incident_data.get('severity_score', 3)),
        "risk": get_risk(incident_data.get('severity_score', 3)),
        "u_outageshield_incident_id": incident_data.get('incident_id', ''),
        "state": "-5",  # New
        "approval": "requested"
    }
    
    # Create request
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    
    # Add headers
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            change_number = result.get('result', {}).get('number', 'UNKNOWN')
            sys_id = result.get('result', {}).get('sys_id', '')
            print(f"Created ServiceNow change request: {change_number}")
            return {'number': change_number, 'sys_id': sys_id}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        print(f"ServiceNow HTTP error {e.code}: {error_body}")
        return None
    except Exception as e:
        print(f"ServiceNow request failed: {e}")
        return None


def build_description(data):
    """Build ServiceNow change request description"""
    desc = "=== OUTAGESHIELD AI INCIDENT ===\\n\\n"
    desc += f"Incident ID: {data.get('incident_id', 'N/A')}\\n"
    desc += f"Service: {data.get('service', 'N/A')}\\n"
    desc += f"Severity: {data.get('severity_score', 'N/A')}/5\\n\\n"
    
    if data.get('root_cause'):
        desc += f"ROOT CAUSE:\\n{data.get('root_cause')}\\n\\n"
    
    if data.get('proposed_action'):
        action = data.get('proposed_action')
        if isinstance(action, dict):
            desc += f"PROPOSED ACTION:\\n{action.get('description', str(action))}\\n"
        else:
            desc += f"PROPOSED ACTION:\\n{action}\\n"
    
    desc += f"\\nDASHBOARD: {DASHBOARD_URL}/incidents/{data.get('incident_id')}"
    return desc


def get_priority(severity):
    if severity >= 5: return "1"
    if severity >= 4: return "2"
    if severity >= 3: return "3"
    return "4"


def get_risk(severity):
    if severity >= 4: return "High"
    if severity >= 3: return "Moderate"
    return "Low"


def lambda_handler(event, context):
    """
    Invoked by Step Functions with waitForTaskToken.
    Stores task token, creates ServiceNow change request, updates incident status.
    """
    print(f"Received event: {json.dumps(event, default=str)}")
    
    task_token = event.get('task_token')
    incident_id = event.get('incident_id')
    service = event.get('service', 'unknown')
    severity_score = event.get('severity_score', 3)
    proposed_action = event.get('proposed_action', {})
    risk_level = event.get('risk_level', 'medium')
    workflow_id = event.get('workflow_id', '')

    if not task_token or not incident_id:
        print("ERROR: Missing task_token or incident_id")
        return

    approval_id = incident_id

    # Store token in DynamoDB
    table = dynamodb.Table(APPROVALS_TABLE)
    action_str = json.dumps(proposed_action) if isinstance(proposed_action, dict) else str(proposed_action or '')
    
    approval_item = {
        'approval_id': approval_id,
        'incident_id': incident_id,
        'task_token': task_token,
        'service': service,
        'severity_score': int(severity_score) if severity_score else 3,
        'proposed_action': action_str,
        'risk_level': str(risk_level) if risk_level else 'medium',
        'workflow_id': workflow_id,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'ttl': int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
    }
    
    # Create ServiceNow change request if enabled
    if SERVICENOW_ENABLED:
        incident_data = {
            'incident_id': incident_id,
            'service': service,
            'severity_score': severity_score,
            'proposed_action': proposed_action,
            'root_cause': event.get('root_cause', '')
        }
        sn_result = create_servicenow_change_request(incident_data)
        if sn_result:
            approval_item['servicenow_change'] = sn_result.get('number')
            approval_item['servicenow_sys_id'] = sn_result.get('sys_id')
    
    table.put_item(Item=approval_item)
    print(f"Stored task token for incident {incident_id}")

    # Update incident status to "Awaiting Approval"
    try:
        incidents_table = dynamodb.Table(INCIDENTS_TABLE)
        update_expr = 'SET #s = :status, awaiting_approval_since = :ts, workflow_step = :ws'
        expr_values = {
            ':status': 'Awaiting Approval',
            ':ts': datetime.now(timezone.utc).isoformat(),
            ':ws': 'awaiting_approval'
        }
        
        if approval_item.get('servicenow_change'):
            update_expr += ', servicenow_change = :sn'
            expr_values[':sn'] = approval_item['servicenow_change']
        
        incidents_table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues=expr_values
        )
        print(f"Updated incident {incident_id} status to Awaiting Approval")
    except Exception as e:
        print(f"Failed to update incident status: {e}")

    # Send SNS notification
    approve_url = f"{DASHBOARD_URL}/incidents/{incident_id}"
    action_desc = ''
    if isinstance(proposed_action, dict):
        action_desc = proposed_action.get('description', str(proposed_action))
    else:
        action_desc = str(proposed_action) if proposed_action else 'Review recommended actions'

    sn_info = ""
    if approval_item.get('servicenow_change'):
        sn_info = f"\\nServiceNow Change: {approval_item['servicenow_change']}"

    message = f"REMEDIATION APPROVAL REQUIRED\\n\\nIncident: {incident_id}\\nService: {service}\\nSeverity: {severity_score}/5{sn_info}\\n\\nProposed Action:\\n{action_desc}\\n\\nDashboard: {approve_url}"

    if APPROVAL_TOPIC_ARN:
        try:
            sns.publish(TopicArn=APPROVAL_TOPIC_ARN, Subject=f"[APPROVAL NEEDED] {service} - {incident_id}", Message=message)
        except Exception as e:
            print(f"Failed to send SNS: {e}")

    print(f"Approval request created. Workflow paused.")
'''

# Create deployment package
import zipfile
import io

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', approval_lambda_code)
zip_buffer.seek(0)

try:
    lambda_client.update_function_code(
        FunctionName='outageshield-approval-dev',
        ZipFile=zip_buffer.read()
    )
    print("   ✅ Updated approval Lambda with ServiceNow integration")
    
    # Wait for the code update to complete
    print("   ⏳ Waiting for Lambda to be ready...")
    import time
    time.sleep(10)
    
    # Update environment variables
    lambda_client.update_function_configuration(
        FunctionName='outageshield-approval-dev',
        Environment={
            'Variables': {
                'APPROVALS_TABLE': 'outageshield-approvals-dev',
                'INCIDENTS_TABLE': 'outageshield-incidents-dev',
                'APPROVAL_TOPIC_ARN': 'arn:aws:sns:us-east-1:193786182229:outageshield-alerts-dev',
                'DASHBOARD_URL': 'https://d2k1km1tzlio49.cloudfront.net',
                'SERVICENOW_ENABLED': 'true'
            }
        }
    )
    print("   ✅ Enabled ServiceNow integration")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Step 4: Add SSM permissions to Lambda role
print("\n4. Adding SSM permissions to Lambda role...")
iam = boto3.client('iam')
try:
    ssm_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter"
                ],
                "Resource": [
                    "arn:aws:ssm:us-east-1:*:parameter/outageshield/servicenow/*"
                ]
            }
        ]
    }
    iam.put_role_policy(
        RoleName='outageshield-approval-role-dev',
        PolicyName='ServiceNowSSMAccess',
        PolicyDocument=json.dumps(ssm_policy)
    )
    print("   ✅ Added SSM permissions")
except Exception as e:
    print(f"   ⚠️ {e}")

print("\n" + "=" * 60)
print("SETUP COMPLETE!")
print("=" * 60)
print(f"""
ServiceNow Integration is now active:

Instance: https://{SERVICENOW_INSTANCE}
Credentials stored in: AWS SSM Parameter Store

When an incident reaches approval:
1. Task token stored in DynamoDB
2. Change Request created in ServiceNow
3. Incident status set to "Awaiting Approval"
4. SNS notification sent

You can approve via:
- OutageShield Dashboard
- ServiceNow (once you set up the callback)

To test:
1. Go to https://{SERVICENOW_INSTANCE}
2. Login with your credentials
3. Navigate to Change > All
4. You should see OutageShield change requests

Next: Set up ServiceNow callback (see docs/servicenow-setup.md)
""")
