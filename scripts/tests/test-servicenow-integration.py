"""
Test ServiceNow Integration - End-to-End Approval Flow

This test:
1. Creates a test incident in DynamoDB
2. Invokes the approval Lambda (which creates a ServiceNow Change Request)
3. Shows you the ServiceNow link to approve/reject
4. Monitors for the callback

Run this and then approve/reject in ServiceNow to test the full flow.
"""

import boto3
import json
import uuid
import time
from datetime import datetime, timezone

# AWS clients
lambda_client = boto3.client('lambda', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')
sfn = boto3.client('stepfunctions', region_name='us-east-1')

# Get ServiceNow instance
try:
    sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
except:
    sn_instance = 'dev252089.service-now.com'

print("=" * 70)
print("SERVICENOW INTEGRATION TEST")
print("=" * 70)
print(f"ServiceNow Instance: https://{sn_instance}")
print(f"Started: {datetime.now().isoformat()}")
print("=" * 70)

# Generate test incident
incident_id = f"INC-SN-TEST-{str(uuid.uuid4())[:6].upper()}"
print(f"\n📋 Test Incident ID: {incident_id}")

# Step 1: Create test incident in DynamoDB
print("\n" + "-" * 70)
print("STEP 1: Creating test incident in DynamoDB")
print("-" * 70)

incidents_table = dynamodb.Table('outageshield-incidents-dev')

test_incident = {
    'incident_id': incident_id,
    'service': 'payment-service',
    'alarm_name': 'HighLatency-payment-service-TEST',
    'status': 'Analyzing',
    'severity_score': 4,
    'business_impact_score': 8,
    'affected_users': 50000,
    'revenue_at_risk': '$10,000/hour',
    'root_cause': 'Database connection pool exhaustion due to increased traffic',
    'rca_category': 'capacity',
    'confidence': 85,
    'created_at': datetime.now(timezone.utc).isoformat(),
    'workflow_step': 'rca_complete',
    'ai_summary': 'The payment service is experiencing high latency due to database connection pool exhaustion. This is affecting approximately 50,000 users and putting $10,000/hour revenue at risk.',
    'recommendations': [
        {
            'description': 'Scale up database connection pool from 100 to 200 connections',
            'category': 'scaling',
            'confidence': 90,
            'risk_level': 'low'
        },
        {
            'description': 'Enable auto-scaling for the payment service',
            'category': 'automation',
            'confidence': 85,
            'risk_level': 'low'
        }
    ]
}

try:
    incidents_table.put_item(Item=test_incident)
    print(f"   ✅ Created incident: {incident_id}")
except Exception as e:
    print(f"   ❌ Failed to create incident: {e}")
    exit(1)

# Step 2: Simulate Step Functions calling the approval Lambda
print("\n" + "-" * 70)
print("STEP 2: Invoking Approval Lambda (simulating Step Functions)")
print("-" * 70)

# Create a fake task token (in real workflow, Step Functions provides this)
fake_task_token = f"test-token-{uuid.uuid4()}"

approval_event = {
    'task_token': fake_task_token,
    'incident_id': incident_id,
    'service': 'payment-service',
    'severity_score': 4,
    'proposed_action': {
        'type': 'scale_database',
        'description': 'Scale up database connection pool from 100 to 200 connections',
        'risk_level': 'low',
        'estimated_time': '5 minutes'
    },
    'risk_level': 'low',
    'root_cause': 'Database connection pool exhaustion',
    'workflow_id': f'test-workflow-{uuid.uuid4()}'
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-approval-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(approval_event)
    )
    result = json.loads(response['Payload'].read().decode('utf-8'))
    print(f"   ✅ Approval Lambda invoked successfully")
    print(f"   Response: {json.dumps(result, indent=2)[:500]}")
except Exception as e:
    print(f"   ❌ Failed to invoke approval Lambda: {e}")

# Step 3: Check what was created
print("\n" + "-" * 70)
print("STEP 3: Checking created records")
print("-" * 70)

# Check approvals table
approvals_table = dynamodb.Table('outageshield-approvals-dev')
try:
    approval_record = approvals_table.get_item(Key={'approval_id': incident_id})
    if 'Item' in approval_record:
        item = approval_record['Item']
        print(f"   ✅ Approval record created:")
        print(f"      - Status: {item.get('status')}")
        print(f"      - Task Token: {item.get('task_token', '')[:30]}...")
        if item.get('servicenow_change'):
            print(f"      - ServiceNow Change: {item.get('servicenow_change')}")
    else:
        print(f"   ⚠️ No approval record found")
except Exception as e:
    print(f"   ❌ Error checking approvals: {e}")

# Check incident status
try:
    incident_record = incidents_table.get_item(Key={'incident_id': incident_id})
    if 'Item' in incident_record:
        item = incident_record['Item']
        print(f"\n   ✅ Incident updated:")
        print(f"      - Status: {item.get('status')}")
        print(f"      - Workflow Step: {item.get('workflow_step')}")
        if item.get('servicenow_change'):
            print(f"      - ServiceNow Change: {item.get('servicenow_change')}")
except Exception as e:
    print(f"   ❌ Error checking incident: {e}")

# Step 4: Check ServiceNow for the change request
print("\n" + "-" * 70)
print("STEP 4: Checking ServiceNow for Change Request")
print("-" * 70)

import base64
import urllib.request
import urllib.error

try:
    username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
    password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
    
    # Search for the change request
    url = f"https://{sn_instance}/api/now/table/change_request?sysparm_query=u_outageshield_incident_id={incident_id}&sysparm_limit=1"
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())
        changes = result.get('result', [])
        
        if changes:
            change = changes[0]
            change_number = change.get('number')
            sys_id = change.get('sys_id')
            print(f"   ✅ ServiceNow Change Request found!")
            print(f"      - Change Number: {change_number}")
            print(f"      - State: {change.get('state')}")
            print(f"      - Approval: {change.get('approval')}")
            print(f"\n   🔗 APPROVE/REJECT HERE:")
            print(f"      https://{sn_instance}/change_request.do?sys_id={sys_id}")
        else:
            print(f"   ⚠️ No ServiceNow change request found for {incident_id}")
            print(f"      This may be because ServiceNow integration is disabled")
            print(f"      or the approval Lambda doesn't have ServiceNow enabled")
            
except Exception as e:
    print(f"   ❌ Error checking ServiceNow: {e}")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"""
Incident ID: {incident_id}
ServiceNow Instance: https://{sn_instance}

NEXT STEPS:
1. Go to ServiceNow and find the change request
2. Click "OutageShield Approve" or "OutageShield Reject"
3. Check the work notes for the callback result

NOTE: Since this is a test with a fake task token, the callback to 
Step Functions will fail (expected). In a real workflow, the callback
would resume the Step Functions execution.

To test with a REAL workflow, run:
   python scripts/tests/full-workflow-test.py

This will trigger the actual Step Functions workflow which will pause
at the approval step and wait for your ServiceNow approval.
""")
print("=" * 70)
