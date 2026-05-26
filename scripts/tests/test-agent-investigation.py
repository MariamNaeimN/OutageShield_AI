"""Test agent investigation for a specific incident."""
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-incidents-dev')

# Get an incident with a known good service
inc_id = 'INC-AB122B50'  # dashboard-api incident
response = table.get_item(Key={'incident_id': inc_id})
item = response.get('Item', {})

if not item:
    print(f"Incident {inc_id} not found")
    exit(1)

print(f"Testing agent investigation for: {inc_id}")
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
root_cause = item.get('root_cause', '')
if root_cause:
    event['step3']['root_causes'] = [{'description': root_cause}]

print(f"Invoking agent-invoker Lambda...")

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
print(f"\nInvestigation:\n{investigation}")

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
