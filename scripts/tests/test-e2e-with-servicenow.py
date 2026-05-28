"""
End-to-End Test with ServiceNow Integration
Tests the full workflow and syncs all data to ServiceNow
"""
import boto3
import json
import time
import uuid
from datetime import datetime, timezone

sfn = boto3.client('stepfunctions', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')

# Generate unique incident ID
incident_id = f"INC-E2E-{str(uuid.uuid4())[:6].upper()}"

print("=" * 60)
print("END-TO-END TEST WITH SERVICENOW")
print("=" * 60)
print(f"Incident ID: {incident_id}")
print(f"Started: {datetime.now().isoformat()}")
print("=" * 60)

# Test input - simulates a CloudWatch alarm
test_input = {
    "source": "aws.cloudwatch",
    "detail-type": "CloudWatch Alarm State Change",
    "detail": {
        "alarmName": f"HighLatency-payment-service-{incident_id}",
        "state": {
            "value": "ALARM",
            "reason": "Threshold Crossed: P99 latency 2500ms exceeded 1000ms threshold"
        },
        "previousState": {"value": ""},
        "configuration": {
            "metrics": [{"metricName": "Duration", "namespace": "AWS/Lambda"}]
        },
        "trigger": {
            "MetricName": "Duration",
            "Namespace": "AWS/Lambda",
            "Dimensions": [{"name": "FunctionName", "value": "payment-service"}]
        },
        "stateChangeTime": datetime.now(timezone.utc).isoformat()
    }
}

# Start the workflow
print("\n1. Starting Step Functions workflow...")
state_machine_arn = "arn:aws:states:us-east-1:193786182229:stateMachine:outageshield-workflow-dev"

try:
    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=f"test-{incident_id}-{int(time.time())}",
        input=json.dumps(test_input)
    )
    execution_arn = response['executionArn']
    print(f"   ✅ Workflow started: {execution_arn.split(':')[-1]}")
except Exception as e:
    print(f"   ❌ Failed to start workflow: {e}")
    exit(1)

# Wait for workflow to reach approval step
print("\n2. Waiting for workflow to reach approval step...")
max_wait = 180  # 3 minutes
start_time = time.time()

while time.time() - start_time < max_wait:
    response = sfn.describe_execution(executionArn=execution_arn)
    status = response['status']
    
    if status == 'RUNNING':
        # Check if waiting for approval
        try:
            history = sfn.get_execution_history(
                executionArn=execution_arn,
                maxResults=50,
                reverseOrder=True
            )
            for event in history['events']:
                if event['type'] == 'TaskStateEntered':
                    state_name = event.get('stateEnteredEventDetails', {}).get('name', '')
                    if 'Approval' in state_name:
                        print(f"   ✅ Workflow paused at: {state_name}")
                        break
        except:
            pass
        
        # Check DynamoDB for incident
        incidents_table = dynamodb.Table('outageshield-incidents-dev')
        try:
            result = incidents_table.get_item(Key={'incident_id': incident_id})
            if result.get('Item'):
                item = result['Item']
                if item.get('servicenow_change'):
                    print(f"   ✅ ServiceNow Change: {item.get('servicenow_change')}")
                    break
                if item.get('status') == 'Awaiting Approval':
                    print(f"   ⏳ Status: Awaiting Approval")
        except:
            pass
    elif status == 'SUCCEEDED':
        print(f"   ✅ Workflow completed!")
        break
    elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
        print(f"   ❌ Workflow {status}")
        break
    
    elapsed = int(time.time() - start_time)
    print(f"   ⏳ Waiting... ({elapsed}s)", end='\r')
    time.sleep(5)

print()

# Get incident data
print("\n3. Getting incident data from DynamoDB...")
incidents_table = dynamodb.Table('outageshield-incidents-dev')
result = incidents_table.get_item(Key={'incident_id': incident_id})
incident = result.get('Item', {})

if incident:
    print(f"   Incident ID: {incident.get('incident_id')}")
    print(f"   Service: {incident.get('service')}")
    print(f"   Status: {incident.get('status')}")
    print(f"   Severity: {incident.get('severity_score')}/5")
    print(f"   Business Impact: {incident.get('business_impact_score')}/10")
    print(f"   Root Cause: {str(incident.get('root_cause', ''))[:60]}...")
    print(f"   ServiceNow Change: {incident.get('servicenow_change', 'N/A')}")
    
    change_number = incident.get('servicenow_change')
else:
    print("   ❌ Incident not found in DynamoDB")
    change_number = None

# Get AI reasoning
print("\n4. Getting AI reasoning data...")
ai_table = dynamodb.Table('outageshield-ai-reasoning-dev')
try:
    ai_result = ai_table.query(
        KeyConditionExpression='incident_id = :iid',
        ExpressionAttributeValues={':iid': incident_id},
        Limit=1
    )
    if ai_result.get('Items'):
        ai = ai_result['Items'][0]
        print(f"   AI Summary: {str(ai.get('ai_summary', ''))[:80]}...")
        print(f"   Investigation: {str(ai.get('investigation_summary', ''))[:80]}...")
        
        qa = ai.get('quick_actions', '[]')
        if isinstance(qa, str):
            qa = json.loads(qa)
        print(f"   Quick Actions: {len(qa)} found")
except Exception as e:
    print(f"   ⚠️ No AI reasoning: {e}")

# Sync to ServiceNow
if change_number:
    print(f"\n5. Syncing all data to ServiceNow ({change_number})...")
    
    import base64
    import urllib.request
    import urllib.error
    
    sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
    username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
    password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    # Get AI reasoning for sync
    ai_reasoning = None
    try:
        ai_result = ai_table.query(
            KeyConditionExpression='incident_id = :iid',
            ExpressionAttributeValues={':iid': incident_id},
            Limit=1
        )
        if ai_result.get('Items'):
            ai_reasoning = ai_result['Items'][0]
    except:
        pass
    
    # Build investigation text
    investigation_parts = []
    if incident.get('agent_investigation'):
        investigation_parts.append("AGENT INVESTIGATION:")
        investigation_parts.append(str(incident.get('agent_investigation')))
    if ai_reasoning and ai_reasoning.get('investigation_summary'):
        investigation_parts.append(f"\nINVESTIGATION SUMMARY:\n{ai_reasoning.get('investigation_summary')}")
    if incident.get('scoring_reasoning'):
        investigation_parts.append(f"\nBUSINESS IMPACT ANALYSIS:\n{incident.get('scoring_reasoning')}")
    investigation_text = "\n".join(investigation_parts)[:3900]
    
    # Build AI summary with quick actions
    ai_summary_parts = []
    if ai_reasoning and ai_reasoning.get('ai_summary'):
        ai_summary_parts.append(str(ai_reasoning.get('ai_summary')))
    if ai_reasoning and ai_reasoning.get('recommended_action'):
        try:
            rec = ai_reasoning.get('recommended_action')
            if isinstance(rec, str):
                rec = json.loads(rec)
            ai_summary_parts.append(f"\n\nRECOMMENDED ACTION:")
            ai_summary_parts.append(f"Type: {rec.get('type', 'N/A')}")
            ai_summary_parts.append(f"Confidence: {rec.get('confidence', 'N/A')}%")
        except:
            pass
    if ai_reasoning and ai_reasoning.get('quick_actions'):
        try:
            qa = ai_reasoning.get('quick_actions')
            if isinstance(qa, str):
                qa = json.loads(qa)
            if qa:
                ai_summary_parts.append(f"\n\nQUICK ACTIONS ({len(qa)} available):")
                for i, action in enumerate(qa[:8], 1):
                    ai_summary_parts.append(f"  {i}. {action.get('label', '')}")
        except:
            pass
    ai_summary_text = "\n".join(ai_summary_parts)[:3900]
    
    # Get sys_id
    url = f"https://{sn_instance}/api/now/table/change_request?sysparm_query=number={change_number}&sysparm_limit=1"
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            if result.get('result'):
                sys_id = result['result'][0]['sys_id']
                
                # Update ServiceNow
                update_payload = {
                    "u_outageshield_investigation": investigation_text,
                    "u_outageshield_ai_summary": ai_summary_text,
                    "u_outageshield_affected_users": str(incident.get('affected_users', '')),
                    "u_outageshield_revenue_risk": str(incident.get('revenue_at_risk', '')),
                    "u_outageshield_business_impact": f"{incident.get('business_impact_score', 'N/A')}/10",
                    "u_outageshield_confidence": f"{incident.get('confidence', 'N/A')}%",
                    "u_outageshield_category": incident.get('rca_category', ''),
                    "u_outageshield_dashboard_url": f"https://d2k1km1tzlio49.cloudfront.net/incidents/{incident_id}"
                }
                
                data = json.dumps(update_payload).encode('utf-8')
                update_url = f"https://{sn_instance}/api/now/table/change_request/{sys_id}"
                req = urllib.request.Request(update_url, data=data, method='PATCH')
                req.add_header('Authorization', f'Basic {credentials}')
                req.add_header('Content-Type', 'application/json')
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    print("   ✅ ServiceNow updated with all data!")
    except Exception as e:
        print(f"   ⚠️ ServiceNow sync error: {e}")

# Print summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']

print(f"""
Incident ID: {incident_id}
Service: {incident.get('service', 'N/A')}
Status: {incident.get('status', 'N/A')}
Severity: {incident.get('severity_score', 'N/A')}/5
Business Impact: {incident.get('business_impact_score', 'N/A')}/10

ServiceNow Change: {change_number or 'N/A'}

LINKS:
- OutageShield Dashboard: https://d2k1km1tzlio49.cloudfront.net/incidents/{incident_id}
- ServiceNow Change: https://{sn_instance}/change_request.do?sysparm_query=number={change_number}
- ServiceNow OutageShield View: https://{sn_instance}/outageshield_incident.do?number={change_number}

NEXT STEPS:
1. Open ServiceNow link above
2. Review the OutageShield AI Analysis section
3. Click "View in OutageShield" button for dashboard view
4. Approve or Reject the change request
5. Workflow will resume automatically after approval
""")

print("=" * 60)
