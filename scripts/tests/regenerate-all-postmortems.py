"""
Regenerate postmortems for ALL incidents with AI-generated prevention recommendations.
Updates existing postmortems instead of creating duplicates.
"""
import boto3
import json
import time
from decimal import Decimal
from datetime import datetime, timezone

lambda_client = boto3.client('lambda', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

incidents_table = dynamodb.Table('outageshield-incidents-dev')
postmortems_table = dynamodb.Table('outageshield-postmortems-dev')

# Helper to convert Decimal to int/float for JSON serialization
def decimal_default(obj):
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

print("=" * 70)
print("REGENERATING POSTMORTEMS FOR ALL INCIDENTS")
print("=" * 70)

# Step 1: Get all incidents
print("\n[STEP 1] Fetching all incidents...")
response = incidents_table.scan()
incidents = response.get('Items', [])

while 'LastEvaluatedKey' in response:
    response = incidents_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    incidents.extend(response.get('Items', []))

print(f"   Found {len(incidents)} incidents")

# Step 2: Delete existing postmortems to avoid duplicates
print("\n[STEP 2] Clearing existing postmortems...")
pm_response = postmortems_table.scan()
pm_items = pm_response.get('Items', [])

while 'LastEvaluatedKey' in pm_response:
    pm_response = postmortems_table.scan(ExclusiveStartKey=pm_response['LastEvaluatedKey'])
    pm_items.extend(pm_response.get('Items', []))

deleted = 0
for pm in pm_items:
    try:
        postmortems_table.delete_item(Key={'postmortem_id': pm['postmortem_id']})
        deleted += 1
    except Exception as e:
        print(f"   Error deleting {pm.get('postmortem_id')}: {e}")

print(f"   Deleted {deleted} existing postmortems")

# Step 3: Regenerate postmortems for each incident
print("\n[STEP 3] Regenerating postmortems...")
success = 0
failed = 0

for i, incident in enumerate(incidents):
    incident_id = incident.get('incident_id', '')
    service = incident.get('service', 'unknown')
    
    if not incident_id:
        continue
    
    # Build the event payload for postmortem lambda
    # Get root causes
    root_causes_raw = incident.get('root_causes_raw', '[]')
    try:
        root_causes = json.loads(root_causes_raw) if root_causes_raw else []
    except:
        root_causes = []
    
    # Get recommendations
    recommendations_raw = incident.get('recommendations_raw', '[]')
    try:
        recommendations = json.loads(recommendations_raw) if recommendations_raw else []
    except:
        recommendations = []
    
    # Build event
    event = {
        'incident_id': incident_id,
        'service': service,
        'signal': {
            'signal_id': incident_id,
            'service': service,
            'alarm_name': incident.get('alarm_name', ''),
            'severity_score': incident.get('severity_score', 3)
        },
        'step2': {
            'severity_score': incident.get('severity_score', 3),
            'affected_users': incident.get('affected_users', 0),
            'revenue_at_risk': incident.get('revenue_at_risk', 'Unknown')
        },
        'step3': {
            'root_causes': root_causes
        },
        'step3b': {
            'investigation': incident.get('agent_investigation', '')
        },
        'step4': {
            'recommendations': recommendations
        }
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName='outageshield-postmortem-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(event, default=decimal_default)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        
        if result.get('statusCode') == 200:
            success += 1
            if (i + 1) % 10 == 0:
                print(f"   [{i+1}/{len(incidents)}] ✓ {incident_id} ({service})")
        else:
            failed += 1
            print(f"   [{i+1}/{len(incidents)}] ✗ {incident_id}: {result}")
    except Exception as e:
        failed += 1
        print(f"   [{i+1}/{len(incidents)}] ✗ {incident_id}: {e}")
    
    # Small delay to avoid throttling Bedrock
    if (i + 1) % 5 == 0:
        time.sleep(1)

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"   ✓ Postmortems generated: {success}")
print(f"   ✗ Failed: {failed}")
print(f"   Total incidents: {len(incidents)}")

# Verify
print("\n[VERIFICATION]")
pm_count = postmortems_table.scan(Select='COUNT')['Count']
print(f"   Postmortems in table: {pm_count}")

print("\n" + "=" * 70)
print("DONE!")
print("=" * 70)
