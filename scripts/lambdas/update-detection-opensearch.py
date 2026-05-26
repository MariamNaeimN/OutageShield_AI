"""Update detection Lambda to store richer docs in OpenSearch."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
from datetime import datetime, timezone
import uuid

stepfunctions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'outageshield-events-dev')
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')

THRESHOLDS = {'latency_ms': 500, 'error_rate_pct': 5, 'cpu_pct': 85}

def lambda_handler(event, context):
    signal = None
    if is_alarm_event(event):
        signal = generate_signal(event, 'metric')
    elif is_log_error(event):
        signal = generate_signal(event, 'log')
    elif is_latency_anomaly(event):
        signal = generate_signal(event, 'trace')

    if signal:
        store_event(signal, event)
        index_to_opensearch(signal, event)
        start_workflow(signal)
        return {'statusCode': 200, 'workflow_started': True, 'signal_id': signal['signal_id']}
    return {'statusCode': 200, 'workflow_started': False}

def is_alarm_event(event):
    detail = event.get('detail', {})
    return detail.get('state', {}).get('value') == 'ALARM'

def is_log_error(event):
    detail = event.get('detail', {})
    message = str(detail.get('message', ''))
    return any(p in message for p in ['ERROR', 'FATAL', 'OutOfMemory', 'Timeout'])

def is_latency_anomaly(event):
    detail = event.get('detail', {})
    return detail.get('latency_ms', 0) > THRESHOLDS['latency_ms']

def generate_signal(event, detection_type):
    detail = event.get('detail', {})
    alarm_name = detail.get('alarmName', '')
    # Extract service: everything after the first dash (e.g. "HighLatency-payments-api" -> "payments-api")
    if alarm_name and '-' in alarm_name:
        service = alarm_name.split('-', 1)[1]  # "payments-api", "checkout-service", etc.
    else:
        service = (detail.get('resourceId') or
                   detail.get('requestParameters', {}).get('functionName') or
                   detail.get('service') or
                   alarm_name or
                   'unknown-service')
    return {
        'signal_id': 'INC-' + str(uuid.uuid4())[:8].upper(),
        'service': service,
        'alarm_name': alarm_name,  # Pass alarm_name through for runbook lookup
        'detection_type': detection_type,
        'severity_score': calculate_severity(detail),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'auto_remediation_enabled': False,
        'source_event_summary': json.dumps(detail, default=str)[:500]
    }

def calculate_severity(detail):
    if detail.get('state', {}).get('value') == 'ALARM':
        return 4
    return 3

def store_event(signal, raw_event):
    try:
        table = dynamodb.Table(EVENTS_TABLE)
        detail = raw_event.get('detail', {})
        table.put_item(Item={
            'event_id': signal['signal_id'],
            'service': signal['service'],
            'source': raw_event.get('source', 'aws.cloudwatch'),
            'detection_type': signal['detection_type'],
            'severity': str(signal['severity_score']),
            'alarm_name': detail.get('alarmName', ''),
            'reason': detail.get('state', {}).get('reason', ''),
            'timestamp': signal['timestamp'],
            'raw_event': json.dumps(detail, default=str)[:1000]
        })
    except Exception as e:
        print(f"Store event failed: {e}")

def start_workflow(signal):
    try:
        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=signal['signal_id'],
            input=json.dumps({'signal': signal})
        )
        print(f"Workflow started: {signal['signal_id']}")
    except Exception as e:
        print(f"Failed to start workflow: {e}")

def index_to_opensearch(signal, raw_event):
    if not OPENSEARCH_ENDPOINT:
        return
    try:
        from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
        
        host = OPENSEARCH_ENDPOINT.replace('https://', '')
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, 'us-east-1', 'aoss')
        
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        
        detail = raw_event.get('detail', {})
        alarm_name = detail.get('alarmName', '')
        
        # Store enriched document with doc_type for hybrid search
        doc = {
            'doc_type': 'alarm_event',
            'event_id': signal['signal_id'],
            'incident_id': signal['signal_id'],
            'service': signal['service'],
            'full_service_name': alarm_name.split('-', 1)[1] if '-' in alarm_name else signal['service'],
            'detection_type': signal['detection_type'],
            'severity': signal['severity_score'],
            'alarm_name': alarm_name,
            'alarm_type': alarm_name.split('-')[0] if '-' in alarm_name else '',
            'reason': detail.get('state', {}).get('reason', ''),
            'source': raw_event.get('source', 'aws.cloudwatch'),
            'timestamp': signal['timestamp'],
            'message': detail.get('state', {}).get('reason', '')[:500]
        }
        
        client.index(index='outageshield-logs', body=doc, id=signal['signal_id'])
        print(f"Indexed to OpenSearch: {signal['signal_id']}")
    except Exception as e:
        print(f"OpenSearch indexing failed (non-blocking): {e}")
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating detection Lambda (enriched OpenSearch docs)...")
r = lambda_client.update_function_code(FunctionName='outageshield-detection-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
