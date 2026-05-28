"""Update correlation Lambda to include alarm_name in incident record."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
import uuid
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')

def extract_service(event):
    """Extract service name from event - try multiple sources"""
    signal = event.get('signal', event)
    
    # 1. Try signal.service
    service = signal.get('service')
    if service and service != 'unknown':
        return service
    
    # 2. Try to extract from alarm name
    alarm_name = signal.get('alarm_name', '')
    if not alarm_name:
        detail = event.get('detail', {})
        alarm_name = detail.get('alarmName', '')
    
    if alarm_name and '-' in alarm_name:
        parts = alarm_name.split('-')
        # Skip common prefixes like HighLatency, ErrorRate, etc.
        prefixes = ['HighLatency', 'ErrorRate', 'High', 'Low', 'Critical', 'Warning', 'Alarm', 'Alert']
        service_parts = []
        for part in parts:
            if part in prefixes:
                continue
            if part.startswith('INC') or part.startswith('TEST') or part.startswith('E2E'):
                break
            if len(part) > 2:
                service_parts.append(part)
        if service_parts:
            return '-'.join(service_parts[:2])  # Take first 2 parts as service name
    
    # 3. Try dimensions
    detail = event.get('detail', {})
    trigger = detail.get('trigger', signal.get('trigger', {}))
    dimensions = trigger.get('Dimensions', [])
    for dim in dimensions:
        name = dim.get('name') or dim.get('Name', '')
        if name in ['FunctionName', 'ServiceName', 'TableName']:
            return dim.get('value') or dim.get('Value')
    
    return 'unknown'


def lambda_handler(event, context):
    signal = event.get('signal', event)
    service = extract_service(event)
    incident_id = signal.get('signal_id', 'INC-' + str(uuid.uuid4())[:8].upper())
    alarm_name = signal.get('alarm_name', event.get('detail', {}).get('alarmName', ''))
    now = datetime.now(timezone.utc).isoformat()
    
    print(f"Correlation: Processing incident {incident_id} for service {service}")

    # Query for related alarms in the last hour
    related_alarms = []
    try:
        events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'outageshield-events-dev'))
        response = events_table.query(
            IndexName='service-timestamp-index',
            KeyConditionExpression='service = :svc',
            ExpressionAttributeValues={':svc': service},
            Limit=10,
            ScanIndexForward=False
        )
        related_alarms = response.get('Items', [])
        print(f"Found {len(related_alarms)} related alarms for {service}")
    except Exception as e:
        print(f"Could not query related alarms: {e}")

    incident_context = {
        'context_id': str(uuid.uuid4()),
        'incident_id': incident_id,  # Include incident_id in context
        'signal': signal,
        'service': service,
        'alarm_name': alarm_name,
        'timestamp': now,
        'related_alarms_count': len(related_alarms),
        'related_alarms': related_alarms[:5],  # Top 5 related
        'deployments': [],
        'config_changes': [],
        'past_incidents': [],
        'related_logs': [],
        'unavailable_sources': []
    }

    # Store incident in DynamoDB with alarm_name
    stored_in_dynamo = False
    try:
        inc_table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
        inc_table.put_item(Item={
            'incident_id': incident_id,
            'service': service,
            'alarm_name': alarm_name,
            'title': f"Outage signal on {service}",
            'severity_score': int(signal.get('severity_score', 3)),
            'business_impact_score': 5,
            'status': 'Investigating',
            'created_at': now,
            'updated_at': now,
            'workflow_step': 'correlation',
            'context': json.dumps(incident_context, default=str)
        })
        stored_in_dynamo = True
        print(f"Stored incident {incident_id} in DynamoDB")
    except Exception as e:
        print(f"Failed to store incident: {e}")

    # Store workflow state
    try:
        wf_table = dynamodb.Table(os.environ['WORKFLOW_STATE_TABLE'])
        wf_table.put_item(Item={
            'workflow_id': 'wf-' + incident_id,
            'incident_id': incident_id,
            'current_step': 'correlation',
            'status': 'running',
            'started_at': now,
            'correlation_completed_at': now
        })
    except Exception as e:
        print(f"Failed to store workflow state: {e}")

    return {
        'statusCode': 200, 
        'incident_context': incident_context,
        'incident_id': incident_id,
        'stored_in_dynamo': stored_in_dynamo
    }
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating correlation Lambda to include alarm_name...")
r = lambda_client.update_function_code(FunctionName='outageshield-correlation-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
print("\nNow the incident record will include alarm_name for proper runbook lookup.")
