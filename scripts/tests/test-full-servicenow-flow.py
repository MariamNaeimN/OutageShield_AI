"""
Full End-to-End Test: ServiceNow Approval Flow

This test:
1. Triggers the Step Functions workflow with a test incident
2. Workflow runs through detection, correlation, scoring, RCA, agent investigation
3. Pauses at approval step - creates ServiceNow change request
4. YOU approve in ServiceNow
5. Workflow resumes: remediation, ticket creation, postmortem
6. Results appear in both ServiceNow and Dashboard

Run this and then approve in ServiceNow to see the full flow!
"""

import boto3
import json
import uuid
import time
from datetime import datetime, timezone

# AWS clients
sfn = boto3.client('stepfunctions', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')

# Get ServiceNow instance
try:
    sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
except:
    sn_instance = 'dev252089.service-now.com'

print("=" * 70)
print("FULL END-TO-END TEST: ServiceNow Approval Flow")
print("=" * 70)
print(f"ServiceNow Instance: https://{sn_instance}")
print(f"Started: {datetime.now().isoformat()}")
print("=" * 70)

# Generate unique incident ID
incident_id = f"INC-E2E-{str(uuid.uuid4())[:6].upper()}"
print(f"\n📋 Test Incident ID: {incident_id}")

# Step Functions ARN
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:193786182229:stateMachine:outageshield-workflow-dev'

# Create the input for Step Functions
workflow_input = {
    "source": "test",
    "detail-type": "OutageShield Test Event",
    "detail": {
        "alarmName": f"HighLatency-payment-service-{incident_id}",
        "state": {"value": "ALARM"},
        "configuration": {
            "metrics": [{"metricName": "Latency", "namespace": "AWS/Lambda"}]
        }
    },
    "signal": {
        "signal_id": incident_id,
        "service": "payment-service",
        "alarm_name": f"HighLatency-payment-service-{incident_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metric_name": "Latency",
        "metric_value": 2500,
        "threshold": 1000,
        "region": "us-east-1"
    }
}

print("\n" + "-" * 70)
print("STEP 1: Starting Step Functions Workflow")
print("-" * 70)

try:
    response = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"test-{incident_id}-{int(time.time())}",
        input=json.dumps(workflow_input)
    )
    execution_arn = response['executionArn']
    print(f"   ✅ Workflow started!")
    print(f"   Execution ARN: {execution_arn}")
except Exception as e:
    print(f"   ❌ Failed to start workflow: {e}")
    exit(1)

print("\n" + "-" * 70)
print("STEP 2: Monitoring Workflow Progress")
print("-" * 70)
print("   Workflow will run through:")
print("   1. Detection → 2. Correlation → 3. Scoring → 4. RCA")
print("   5. Agent Investigation → 6. Remediation Recommendations")
print("   7. Summary → 8. APPROVAL (pauses here)")
print()

# Monitor the workflow
max_wait = 300  # 5 minutes max
start_time = time.time()
last_status = ""

while time.time() - start_time < max_wait:
    try:
        response = sfn.describe_execution(executionArn=execution_arn)
        status = response['status']
        
        if status != last_status:
            print(f"   Status: {status}")
            last_status = status
        
        if status == 'RUNNING':
            # Check if we're at the approval step
            approvals_table = dynamodb.Table('outageshield-approvals-dev')
            try:
                result = approvals_table.scan(
                    FilterExpression='incident_id = :iid',
                    ExpressionAttributeValues={':iid': incident_id}
                )
                if result.get('Items'):
                    approval = result['Items'][0]
                    if approval.get('status') == 'pending':
                        print(f"\n   🛑 WORKFLOW PAUSED AT APPROVAL STEP!")
                        print(f"   ServiceNow Change: {approval.get('servicenow_change', 'N/A')}")
                        break
            except:
                pass
            
            time.sleep(5)
            print("   ⏳ Waiting for workflow to reach approval step...")
            
        elif status == 'SUCCEEDED':
            print("   ✅ Workflow completed successfully!")
            break
        elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
            print(f"   ❌ Workflow {status}")
            # Get error details
            if 'error' in response:
                print(f"   Error: {response.get('error')}")
            if 'cause' in response:
                print(f"   Cause: {response.get('cause')}")
            break
    except Exception as e:
        print(f"   Error checking status: {e}")
        time.sleep(5)

# Check for ServiceNow change request
print("\n" + "-" * 70)
print("STEP 3: Checking ServiceNow Change Request")
print("-" * 70)

import base64
import urllib.request

try:
    username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
    password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
    
    # Search for the change request
    url = f"https://{sn_instance}/api/now/table/change_request?sysparm_query=u_outageshield_incident_idLIKE{incident_id}&sysparm_limit=1"
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
            print(f"\n   🔗 APPROVE HERE:")
            print(f"      https://{sn_instance}/change_request.do?sys_id={sys_id}")
        else:
            print(f"   ⚠️ No ServiceNow change request found yet")
            print(f"      The workflow may still be processing...")
            
except Exception as e:
    print(f"   ❌ Error checking ServiceNow: {e}")

# Check incident in DynamoDB
print("\n" + "-" * 70)
print("STEP 4: Checking Incident in Dashboard")
print("-" * 70)

incidents_table = dynamodb.Table('outageshield-incidents-dev')
try:
    # Scan for incidents with our ID pattern
    result = incidents_table.scan(
        FilterExpression='contains(incident_id, :pattern)',
        ExpressionAttributeValues={':pattern': incident_id[:10]}
    )
    incidents = result.get('Items', [])
    
    if incidents:
        inc = incidents[0]
        print(f"   ✅ Incident found in Dashboard!")
        print(f"      - ID: {inc.get('incident_id')}")
        print(f"      - Status: {inc.get('status')}")
        print(f"      - Service: {inc.get('service')}")
        print(f"      - Severity: {inc.get('severity_score')}/5")
        print(f"      - ServiceNow Change: {inc.get('servicenow_change', 'N/A')}")
        
        if inc.get('ai_summary'):
            print(f"\n   AI Summary:")
            print(f"      {inc.get('ai_summary')[:200]}...")
    else:
        print(f"   ⚠️ Incident not found in Dashboard yet")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# Summary
print("\n" + "=" * 70)
print("TEST STATUS")
print("=" * 70)
print(f"""
Incident ID: {incident_id}
Execution ARN: {execution_arn}

NEXT STEPS:
1. Go to ServiceNow and find the change request
2. Click "OutageShield Approve" button (or change Approval field to "Approved")
3. The workflow will automatically resume
4. Check the Dashboard to see:
   - Status change to "Mitigating" then "Resolved"
   - AI Summary and Investigation results
   - Postmortem generated

Dashboard URL: https://d2k1km1tzlio49.cloudfront.net

To monitor the workflow:
   aws stepfunctions describe-execution --execution-arn "{execution_arn}"
""")
print("=" * 70)
