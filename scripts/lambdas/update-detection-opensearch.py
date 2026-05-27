
"""Update detection Lambda to handle both SNS and CloudWatch Events formats."""
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
    """Handle both SNS and CloudWatch Events formats."""
    print(f"Detection event: {json.dumps(event)[:500]}")
    
    # Parse event - handle SNS format first
    parsed_event = parse_event(event)
    
    signal = None
    if is_alarm_event(parsed_event):
        signal = generate_signal(parsed_event, 'metric')
    elif is_log_error(parsed_event):
        signal = generate_signal(parsed_event, 'log')
    elif is_latency_anomaly(parsed_event):
        signal = generate_signal(parsed_event, 'trace')

    if signal:
        store_event(signal, parsed_event)
        index_to_opensearch(signal, parsed_event)
        start_workflow(signal)
        return {
            'statusCode': 200,
            'workflow_started': True,
            'signal': signal,
            'signal_id': signal['signal_id'],
            'is_anomaly': True
        }
    return {'statusCode': 200, 'workflow_started': False, 'is_anomaly': False}


def parse_event(event):
    """Parse event from SNS or CloudWatch Events format."""
    # Check for SNS format
    if 'Records' in event:
        for record in event.get('Records', []):
            if 'Sns' in record:
                message = record['Sns'].get('Message', '{}')
                try:
                    sns_data = json.loads(message) if isinstance(message, str) else message
                    # Convert SNS alarm format to CloudWatch Events format
                    return {
                        'source': 'aws.cloudwatch',
                        'detail-type': 'CloudWatch Alarm State Change',
                        'detail': {
                            'alarmName': sns_data.get('AlarmName', ''),
                            'state': {
                                'value': sns_data.get('NewStateValue', ''),
                                'reason': sns_data.get('NewStateReason', '')
                            },
                            'previousState': {
                                'value': sns_data.get('OldStateValue', '')
                            },
                            'configuration': {
                                'metrics': [{
                                    'metricName': sns_data.get('Trigger', {}).get('MetricName', ''),
                                    'namespace': sns_data.get('Trigger', {}).get('Namespace', '')
                                }]
                            },
                            'trigger': sns_data.get('Trigger', {}),
                            'stateChangeTime': sns_data.get('StateChangeTime', '')
                        }
                    }
                except json.JSONDecodeError:
                    pass
    
    # Already in CloudWatch Events format or direct format
    return event


def is_alarm_event(event):
    detail = event.get('detail', {})
    state_value = detail.get('state', {}).get('value', '')
    return state_value == 'ALARM'


def is_log_error(event):
    detail = event.get('detail', {})
    message = str(detail.get('message', ''))
    reason = str(detail.get('state', {}).get('reason', ''))
    combined = message + reason
    return any(p in combined for p in ['ERROR', 'FATAL', 'OutOfMemory', 'Timeout'])


def is_latency_anomaly(event):
    detail = event.get('detail', {})
    return detail.get('latency_ms', 0) > THRESHOLDS['latency_ms']


def generate_signal(event, detection_type):
    detail = event.get('detail', {})
    alarm_name = detail.get('alarmName', '')
    
    # Extract service: everything after the first dash (e.g. "HighLatency-payments-api" -> "payments-api")
    if alarm_name and '-' in alarm_name:
        service = alarm_name.split('-', 1)[1]
    else:
        # Try other sources
        trigger = detail.get('trigger', {})
        dimensions = trigger.get('Dimensions', [])
        service = None
        for dim in dimensions:
            if dim.get('name') == 'FunctionName' or dim.get('Name') == 'FunctionName':
                service = dim.get('value') or dim.get('Value')
                break
        
        if not service:
            service = (detail.get('resourceId') or
                       detail.get('requestParameters', {}).get('functionName') or
                       detail.get('service') or
                       alarm_name or
                       'unknown-service')
    
    signal = {
        'signal_id': 'INC-' + str(uuid.uuid4())[:8].upper(),
        'service': service,
        'alarm_name': alarm_name,
        'detection_type': detection_type,
        'severity_score': calculate_severity(detail),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'auto_remediation_enabled': False,
        'source_event_summary': json.dumps(detail, default=str)[:500]
    }
    
    print(f"Generated signal: {signal['signal_id']} for service: {service}, alarm: {alarm_name}")
    return signal


def calculate_severity(detail):
    state = detail.get('state', {}).get('value', '')
    reason = detail.get('state', {}).get('reason', '').lower()
    
    # Higher severity for critical keywords
    if 'critical' in reason or 'fatal' in reason:
        return 5
    if state == 'ALARM':
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
            'alarm_name': signal['alarm_name'],
            'reason': detail.get('state', {}).get('reason', ''),
            'timestamp': signal['timestamp'],
            'raw_event': json.dumps(detail, default=str)[:1000]
        })
        print(f"Stored event: {signal['signal_id']}")
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
        alarm_name = signal['alarm_name']
        
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

print("Updating detection Lambda (handles SNS + CloudWatch Events)...")
r = lambda_client.update_function_code(FunctionName='outageshield-detection-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
print()
print("The detection Lambda now handles:")
print("  1. SNS format (Records[].Sns.Message)")
print("  2. CloudWatch Events format (detail.state.value)")
print("  3. Returns signal object in response")
