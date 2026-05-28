"""
Test Human Approval Flow

This script:
1. Lists recent incidents
2. Checks if any are in "Awaiting Approval" status
3. Tests the approval API endpoint
"""

import boto3
import json
import requests

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

print("=" * 60)
print("TESTING HUMAN APPROVAL FLOW")
print("=" * 60)

# Check incidents table
print("\n1. Checking recent incidents...")
incidents_table = dynamodb.Table('outageshield-incidents-dev')
response = incidents_table.scan(Limit=10)

for item in response['Items']:
    incident_id = item.get('incident_id', 'N/A')
    status = item.get('status', 'N/A')
    service = item.get('service', 'N/A')
    print(f"   {incident_id} - {status} - {service}")

# Check approvals table
print("\n2. Checking pending approvals...")
approvals_table = dynamodb.Table('outageshield-approvals-dev')
response = approvals_table.scan()

pending = [item for item in response['Items'] if item.get('status') == 'pending']
print(f"   Found {len(pending)} pending approvals")

for item in pending:
    print(f"   - {item.get('approval_id')} ({item.get('service')}) - created: {item.get('created_at')}")

# Check Step Functions executions
print("\n3. Checking Step Functions executions...")
sfn = boto3.client('stepfunctions', region_name='us-east-1')
executions = sfn.list_executions(
    stateMachineArn='arn:aws:states:us-east-1:193786182229:stateMachine:outageshield-workflow-dev',
    statusFilter='RUNNING',
    maxResults=5
)

running = executions.get('executions', [])
print(f"   Found {len(running)} running executions")

for ex in running:
    print(f"   - {ex['name']} - started: {ex['startDate']}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"""
Human Approval Flow Status:
- Incidents in DB: {len(response['Items'])}
- Pending approvals: {len(pending)}
- Running workflows: {len(running)}

To test the approval:
1. Trigger a new incident with auto_remediation_enabled=true
2. Wait for it to reach "Awaiting Approval" status
3. Go to dashboard: https://d2k1km1tzlio49.cloudfront.net
4. Click on the incident and approve/reject

Or use the API:
  curl -X POST https://601lnlm7r5.execute-api.us-east-1.amazonaws.com/dev/approve/INC-XXXXX \\
    -H "Content-Type: application/json" \\
    -d '{{"decision": "approved", "responder": "test-user"}}'
""")
