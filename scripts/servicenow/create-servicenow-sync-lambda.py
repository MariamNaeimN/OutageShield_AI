"""
Create a Lambda that syncs incident data to ServiceNow
This Lambda can be called after each workflow step to keep ServiceNow updated
"""

import boto3
import json
import zipfile
import io
import time

lambda_client = boto3.client('lambda', region_name='us-east-1')
iam = boto3.client('iam', region_name='us-east-1')

print("=" * 60)
print("CREATING SERVICENOW SYNC LAMBDA")
print("=" * 60)

lambda_code = '''
import json
import boto3
import os
import base64
import urllib.request
import urllib.error

ssm = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')

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


def update_servicenow_change(change_number, work_notes, custom_fields=None):
    """Update a ServiceNow change request with work notes and custom fields"""
    instance, username, password = get_servicenow_config()
    if not instance:
        return False
    
    # Get sys_id for the change request
    url = f"https://{instance}/api/now/table/change_request?sysparm_query=number={change_number}&sysparm_limit=1"
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            if not result.get('result'):
                print(f"Change request {change_number} not found")
                return False
            sys_id = result['result'][0]['sys_id']
    except Exception as e:
        print(f"Error finding change request: {e}")
        return False
    
    # Update the change request
    update_url = f"https://{instance}/api/now/table/change_request/{sys_id}"
    
    update_payload = {"work_notes": work_notes}
    if custom_fields:
        update_payload.update(custom_fields)
    
    data = json.dumps(update_payload).encode('utf-8')
    req = urllib.request.Request(update_url, data=data, method='PATCH')
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"Updated ServiceNow change {change_number}")
            return True
    except Exception as e:
        print(f"Error updating ServiceNow: {e}")
        return False


def lambda_handler(event, context):
    """
    Sync incident data to ServiceNow change request.
    
    Event should contain:
    - incident_id: The OutageShield incident ID
    - change_number: The ServiceNow change request number (optional, will look up)
    - step: Which workflow step just completed (detection, correlation, scoring, rca, agent, remediation, summary, postmortem)
    - data: The data from that step
    """
    print(f"Received event: {json.dumps(event, default=str)[:1000]}")
    
    incident_id = event.get('incident_id')
    change_number = event.get('change_number') or event.get('servicenow_change')
    step = event.get('step', 'update')
    data = event.get('data', {})
    
    if not incident_id:
        return {'statusCode': 400, 'error': 'Missing incident_id'}
    
    # If no change number provided, look it up from the incident
    if not change_number:
        incidents_table = dynamodb.Table(os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev'))
        try:
            result = incidents_table.get_item(Key={'incident_id': incident_id})
            if 'Item' in result:
                change_number = result['Item'].get('servicenow_change')
        except Exception as e:
            print(f"Error looking up incident: {e}")
    
    if not change_number:
        print(f"No ServiceNow change number for incident {incident_id}")
        return {'statusCode': 200, 'message': 'No ServiceNow change to update'}
    
    # Build work notes based on the step
    work_notes = build_work_notes(step, data, incident_id)
    
    # Build custom fields update
    custom_fields = {}
    if step == 'rca' and data.get('root_cause'):
        custom_fields['u_outageshield_root_cause'] = data.get('root_cause', '')[:1000]
    if step == 'summary' and data.get('ai_summary'):
        custom_fields['u_outageshield_recommendation'] = data.get('ai_summary', '')[:2000]
    
    # Update ServiceNow
    success = update_servicenow_change(change_number, work_notes, custom_fields)
    
    return {
        'statusCode': 200 if success else 500,
        'incident_id': incident_id,
        'change_number': change_number,
        'step': step,
        'synced': success
    }


def build_work_notes(step, data, incident_id):
    """Build work notes for a specific workflow step"""
    notes = []
    
    if step == 'detection':
        notes.append("[OutageShield] 🚨 INCIDENT DETECTED")
        notes.append(f"Alarm: {data.get('alarm_name', 'N/A')}")
        notes.append(f"Service: {data.get('service', 'N/A')}")
        notes.append(f"Time: {data.get('timestamp', 'N/A')}")
        
    elif step == 'correlation':
        notes.append("[OutageShield] 🔗 CORRELATION COMPLETE")
        notes.append(f"Related Alarms: {data.get('related_alarms_count', 0)}")
        notes.append(f"Affected Services: {data.get('affected_services', 'N/A')}")
        
    elif step == 'scoring':
        notes.append("[OutageShield] 📊 SEVERITY SCORED")
        notes.append(f"Severity: {data.get('severity_score', 'N/A')}/5")
        notes.append(f"Business Impact: {data.get('business_impact_score', 'N/A')}/10")
        notes.append(f"Affected Users: {data.get('affected_users', 'N/A')}")
        notes.append(f"Revenue at Risk: {data.get('revenue_at_risk', 'N/A')}")
        
    elif step == 'rca':
        notes.append("[OutageShield] 🔍 ROOT CAUSE ANALYSIS")
        notes.append(f"Category: {data.get('rca_category', 'N/A')}")
        notes.append(f"Confidence: {data.get('confidence', 'N/A')}%")
        notes.append(f"Root Cause: {data.get('root_cause', 'N/A')}")
        
    elif step == 'agent':
        notes.append("[OutageShield] 🤖 AI AGENT INVESTIGATION")
        investigation = data.get('investigation', '')
        if len(investigation) > 1500:
            investigation = investigation[:1500] + "... [truncated]"
        notes.append(investigation)
        
    elif step == 'remediation':
        notes.append("[OutageShield] 💡 REMEDIATION RECOMMENDATIONS")
        recs = data.get('recommendations', [])
        for i, rec in enumerate(recs[:5], 1):
            if isinstance(rec, dict):
                notes.append(f"{i}. [{rec.get('category', 'N/A')}] {rec.get('description', '')}")
            else:
                notes.append(f"{i}. {rec}")
                
    elif step == 'summary':
        notes.append("[OutageShield] 📝 AI SUMMARY")
        notes.append(data.get('ai_summary', 'N/A'))
        
    elif step == 'postmortem':
        notes.append("[OutageShield] 📋 POSTMORTEM GENERATED")
        notes.append(f"Summary: {data.get('summary', 'N/A')}")
        notes.append(f"Duration: {data.get('duration', 'N/A')}")
        notes.append(f"Impact: {data.get('impact', 'N/A')}")
        if data.get('prevention'):
            notes.append("Prevention Steps:")
            for i, step in enumerate(data.get('prevention', [])[:3], 1):
                notes.append(f"  {i}. {step}")
                
    elif step == 'resolved':
        notes.append("[OutageShield] ✅ INCIDENT RESOLVED")
        notes.append(f"Resolution: {data.get('resolution', 'N/A')}")
        notes.append(f"Resolved By: {data.get('resolved_by', 'N/A')}")
        
    else:
        notes.append(f"[OutageShield] Update: {step}")
        notes.append(json.dumps(data, default=str)[:1000])
    
    notes.append("")
    notes.append(f"Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/{incident_id}")
    
    return "\\n".join(notes)
'''

# Create deployment package
print("\n1. Creating deployment package...")
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', lambda_code)
zip_buffer.seek(0)

# Check if Lambda exists
print("\n2. Checking if Lambda exists...")
try:
    lambda_client.get_function(FunctionName='outageshield-servicenow-sync-dev')
    exists = True
    print("   Lambda exists, updating...")
except:
    exists = False
    print("   Lambda doesn't exist, creating...")

if exists:
    # Update existing Lambda
    lambda_client.update_function_code(
        FunctionName='outageshield-servicenow-sync-dev',
        ZipFile=zip_buffer.read()
    )
    print("   ✅ Lambda code updated")
else:
    # Get the role ARN from an existing Lambda
    try:
        existing = lambda_client.get_function(FunctionName='outageshield-approval-dev')
        role_arn = existing['Configuration']['Role']
    except:
        role_arn = 'arn:aws:iam::193786182229:role/outageshield-lambda-role-dev'
    
    # Create new Lambda
    lambda_client.create_function(
        FunctionName='outageshield-servicenow-sync-dev',
        Runtime='python3.11',
        Role=role_arn,
        Handler='index.lambda_handler',
        Code={'ZipFile': zip_buffer.read()},
        Timeout=60,
        MemorySize=256,
        Environment={
            'Variables': {
                'INCIDENTS_TABLE': 'outageshield-incidents-dev'
            }
        }
    )
    print("   ✅ Lambda created")

print("\n" + "=" * 60)
print("SERVICENOW SYNC LAMBDA READY!")
print("=" * 60)
print("""
Lambda: outageshield-servicenow-sync-dev

This Lambda can be called to sync data to ServiceNow:

Example invocation:
{
    "incident_id": "INC-123",
    "change_number": "CHG0030005",
    "step": "rca",
    "data": {
        "root_cause": "Database connection pool exhaustion",
        "rca_category": "capacity",
        "confidence": 85
    }
}

Steps supported: detection, correlation, scoring, rca, agent, 
                 remediation, summary, postmortem, resolved
""")
