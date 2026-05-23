"""
Test a single incident through the full pipeline and track each step's output.
Invokes detection Lambda synchronously, waits for workflow, then shows all step results.
"""
import boto3
import json
import time
from decimal import Decimal

REGION = 'us-east-1'
lambda_client = boto3.client('lambda', region_name=REGION)
sf_client = boto3.client('stepfunctions', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

# ─────────────────────────────────────────────────────────────────────────────
# Step 0: Trigger detection
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print("  SINGLE INCIDENT TEST — Full Pipeline Trace")
print("=" * 70)
print()

alarm_event = {
    'source': 'aws.cloudwatch',
    'detail-type': 'CloudWatch Alarm State Change',
    'detail': {
        'alarmName': 'HighLatency-test-api-unique',
        'state': {
            'value': 'ALARM',
            'reason': 'Threshold Crossed: P99 latency (850ms) > threshold (500ms)'
        },
        'previousState': {'value': 'OK'}
    }
}

print("[TRIGGER] Invoking detection Lambda synchronously...")
print(f"  Alarm: HighLatency-test-api-unique")
print(f"  Service: unique (extracted from alarm name)")
print(f"  Reason: P99 latency (850ms) > threshold (500ms)")
print()

r = lambda_client.invoke(
    FunctionName='outageshield-detection-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(alarm_event)
)
detection_result = json.loads(r['Payload'].read().decode())
incident_id = detection_result.get('signal_id', '')

print(f"[DETECTION] Result:")
print(f"  Incident ID: {incident_id}")
print(f"  Workflow started: {detection_result.get('workflow_started')}")
print()

if not incident_id:
    print("ERROR: No incident ID returned. Aborting.")
    exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Wait for workflow to complete
# ─────────────────────────────────────────────────────────────────────────────
print("[WAITING] For Step Functions workflow to complete...")
print("  (Checking every 15s, timeout 5 min)")
print()

sm_arn = f"arn:aws:states:{REGION}:193786182229:stateMachine:outageshield-workflow-dev"
execution_arn = f"arn:aws:states:{REGION}:193786182229:execution:outageshield-workflow-dev:{incident_id}"

start_time = time.time()
status = 'RUNNING'
while status == 'RUNNING' and (time.time() - start_time) < 300:
    try:
        exec_info = sf_client.describe_execution(executionArn=execution_arn)
        status = exec_info['status']
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] Status: {status}")
        if status == 'RUNNING':
            time.sleep(15)
    except Exception as e:
        print(f"  Error checking execution: {e}")
        time.sleep(10)

print()
print(f"[WORKFLOW] Final status: {status}")
print(f"  Duration: {int(time.time() - start_time)}s")
print()

# ─────────────────────────────────────────────────────────────────────────────
# Read the incident from DynamoDB
# ─────────────────────────────────────────────────────────────────────────────
print("[DynamoDB] Reading incident record...")
print()

incidents_table = dynamodb.Table('outageshield-incidents-dev')
response = incidents_table.get_item(Key={'incident_id': incident_id})
incident = response.get('Item', {})

# Display each step's output
print("─" * 70)
print("  STEP-BY-STEP RESULTS")
print("─" * 70)
print()

# Step 1: Correlation
print("[Step 1: CORRELATE]")
print(f"  Service: {incident.get('service', 'N/A')}")
print(f"  Title: {incident.get('title', 'N/A')}")
print(f"  Status: {incident.get('status', 'N/A')}")
print()

# Step 2: Scoring
print("[Step 2: SCORE]")
print(f"  Severity: {incident.get('severity_score', 'N/A')}/5")
print(f"  Business Impact: {incident.get('business_impact_score', 'N/A')}/10")
print(f"  Affected Users: {incident.get('affected_users', 'N/A')}")
print(f"  Revenue at Risk: {incident.get('revenue_at_risk', 'N/A')}")
print(f"  SLA Status: {incident.get('sla_status', 'N/A')}")
print(f"  Reasoning: {str(incident.get('scoring_reasoning', ''))[:200]}")
print()

# Step 3: Root Cause
print("[Step 3: ROOT CAUSE ANALYSIS]")
print(f"  Root Cause: {incident.get('root_cause', 'N/A')}")
print(f"  Confidence: {incident.get('confidence', 'N/A')}%")
root_causes_raw = incident.get('root_causes_raw', '')
if root_causes_raw:
    try:
        rcs = json.loads(root_causes_raw)
        for i, rc in enumerate(rcs[:3]):
            print(f"  [{i+1}] {rc.get('description', '')} (confidence: {rc.get('confidence', '')}%)")
            print(f"      Evidence: {rc.get('evidence', '')[:100]}")
    except:
        pass
print()

# Step 3b: Agent Investigation
print("[Step 3b: AGENT INVESTIGATION]")
agent = incident.get('agent_investigation', '')
if agent:
    print(f"  {agent[:500]}")
else:
    print("  (Agent investigation not available or skipped)")
print()

# Step 4: Recommendations
print("[Step 4: REMEDIATION RECOMMENDATIONS]")
recs_raw = incident.get('recommendations_raw', '')
if recs_raw:
    try:
        recs = json.loads(recs_raw) if isinstance(recs_raw, str) else recs_raw
        if isinstance(recs, list):
            for i, rec in enumerate(recs[:4]):
                if isinstance(rec, dict) and rec.get('category'):
                    print(f"  [{i+1}] {rec.get('category', 'N/A').upper()}: {rec.get('description', '')[:100]}")
                    print(f"      Confidence: {rec.get('confidence', 'N/A')}% | Risk: {rec.get('risk', 'N/A')} | ETR: {rec.get('estimated_ttr_minutes', 'N/A')} min")
                    print(f"      Source: {rec.get('source', 'N/A')}")
                    print(f"      Reasoning: {rec.get('reasoning', '')[:150]}")
                    print()
                else:
                    print(f"  [{i+1}] (invalid format): {str(rec)[:200]}")
                    print()
        else:
            print(f"  Unexpected format: {str(recs)[:300]}")
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw (first 300): {str(recs_raw)[:300]}")
else:
    print("  (No recommendations stored)")
print()

# Step 7: Ticket
print("[Step 7: JIRA TICKET]")
print(f"  Ticket ID: {incident.get('ticket_id', 'N/A')}")
print(f"  Ticket URL: {incident.get('ticket_url', 'N/A')}")
print(f"  Status: {incident.get('ticket_status', 'N/A')}")
print()

# Step 8: Notification
print("[Step 8: SNS NOTIFICATION]")
notif = incident.get('notifications', '')
if notif:
    try:
        n = json.loads(notif)
        print(f"  Type: {n.get('type', 'N/A')}")
        print(f"  Recipient: {n.get('recipient', 'N/A')}")
        print(f"  Subject: {n.get('subject', 'N/A')}")
    except:
        print(f"  Raw: {notif[:200]}")
else:
    print("  (No notification stored)")
print()

# Step 9: Postmortem
print("[Step 9: POSTMORTEM]")
pm_table = dynamodb.Table('outageshield-postmortems-dev')
pm_response = pm_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('incident_id').eq(incident_id))
pms = pm_response.get('Items', [])
if pms:
    pm = pms[0]
    nested = pm.get('postmortem', {}) if isinstance(pm.get('postmortem'), dict) else {}
    print(f"  Postmortem ID: {pm.get('postmortem_id', 'N/A')}")
    print(f"  Root Cause: {nested.get('root_cause', pm.get('root_cause', 'N/A'))}")
    print(f"  Summary: {nested.get('summary', pm.get('summary', 'N/A'))[:200]}")
    print(f"  Duration: {nested.get('duration', pm.get('duration', 'N/A'))}")
    prevention = nested.get('prevention', pm.get('prevention', []))
    if isinstance(prevention, str):
        try: prevention = json.loads(prevention)
        except: prevention = [prevention]
    for i, step in enumerate(prevention[:3]):
        print(f"  Prevention [{i+1}]: {step}")
else:
    print("  (No postmortem generated yet)")
print()

# Final workflow step
print("─" * 70)
print(f"  FINAL WORKFLOW STEP: {incident.get('workflow_step', 'N/A')}")
print(f"  INCIDENT STATUS: {incident.get('status', 'N/A')}")
print("─" * 70)
