"""Re-run agent investigation for a specific incident."""
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-incidents-dev')

# Get the incident
inc_id = 'INC-E6B9ECE4'
response = table.get_item(Key={'incident_id': inc_id})
item = response.get('Item', {})

if not item:
    print(f"Incident {inc_id} not found")
    exit(1)

print(f"Re-running agent investigation for: {inc_id}")
print(f"Service: {item.get('service')}")
print(f"Title: {item.get('title')}")
print("=" * 60)

# Build the event for the agent invoker
event = {
    'signal': {
        'signal_id': inc_id,
        'service': item.get('service', 'unknown'),
        'alarm_name': item.get('title', ''),
        'timestamp': item.get('created_at', '')
    },
    'step3': {
        'root_causes': [],
        'incident_context_id': inc_id
    }
}

# Parse root causes if available
root_causes_raw = item.get('root_causes_raw', '')
if root_causes_raw:
    try:
        event['step3']['root_causes'] = json.loads(root_causes_raw) if isinstance(root_causes_raw, str) else root_causes_raw
    except:
        pass

root_cause = item.get('root_cause', '')
if root_cause and not event['step3']['root_causes']:
    event['step3']['root_causes'] = [{'description': root_cause}]

print(f"Invoking agent-invoker Lambda...")
print(f"Event: {json.dumps(event, indent=2)[:500]}...")

# Invoke the agent invoker Lambda
response = lambda_client.invoke(
    FunctionName='outageshield-agent-invoker-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(event)
)

result = json.loads(response['Payload'].read().decode('utf-8'))
print(f"\n--- Agent Invoker Response ---")
print(f"Status: {result.get('statusCode', 'N/A')}")

investigation = result.get('investigation', '')
print(f"Investigation length: {len(investigation)} chars")
print(f"\nInvestigation preview:\n{investigation[:1500]}...")

# Check sources
sources = []
if '[Source: Incident History' in investigation:
    sources.append('Incident History')
if '[Source: OpenSearch' in investigation:
    sources.append('OpenSearch Logs')
if '[Source: Runbook' in investigation:
    sources.append('Runbook')
if '[Source: Deployment' in investigation:
    sources.append('Deployment History')
print(f"\nSources found: {sources}")

# Now run remediation
print("\n" + "=" * 60)
print("Running remediation Lambda...")

remediation_event = {
    'incident_id': inc_id,
    'service': item.get('service', 'unknown'),
    'alarm_name': item.get('title', ''),
    'agent_investigation': investigation,
    'root_causes': event['step3']['root_causes']
}

response = lambda_client.invoke(
    FunctionName='outageshield-remediation-recommend-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(remediation_event)
)

result = json.loads(response['Payload'].read().decode('utf-8'))
print(f"\n--- Remediation Response ---")
print(f"Status: {result.get('statusCode', 'N/A')}")
print(f"Recommendations: {len(result.get('recommendations', []))}")
print(f"Summary: {result.get('summary', 'N/A')}")

for i, rec in enumerate(result.get('recommendations', []), 1):
    print(f"\n  {i}. [{rec.get('category')}] {rec.get('source')}")
    print(f"     {rec.get('description', '')[:100]}...")
    print(f"     Confidence: {rec.get('confidence')}%, Risk: {rec.get('risk')}")
