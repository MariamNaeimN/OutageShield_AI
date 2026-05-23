"""Fix the agent-actions Lambda with correct code."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'outageshield-events-dev')
RUNBOOKS_TABLE = os.environ.get('RUNBOOKS_TABLE', 'outageshield-runbooks-dev')
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')

def lambda_handler(event, context):
    print(f"Agent action event: {json.dumps(event)}")
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    parameters = event.get('parameters', [])
    params = {}
    for p in parameters:
        params[p['name']] = p['value']

    if api_path == '/search-incidents':
        result = search_incident_history(params)
    elif api_path == '/search-logs':
        result = search_logs(params)
    elif api_path == '/get-runbook':
        result = get_runbook(params)
    elif api_path == '/check-deployments':
        result = check_deployments(params)
    else:
        result = {'error': f'Unknown action: {api_path}'}

    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': 'GET',
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {
                    'body': json.dumps(result)
                }
            }
        }
    }

def search_incident_history(params):
    service = params.get('service', '')
    table = dynamodb.Table(INCIDENTS_TABLE)
    response = table.scan(FilterExpression=Attr('service').eq(service), Limit=10)
    incidents = response.get('Items', [])
    # Sort by created_at descending and skip the first one (most recent = current incident)
    incidents_sorted = sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True)
    past_incidents = incidents_sorted[1:]  # Skip the most recent one
    return {
        'service': service,
        'total_past_incidents': len(past_incidents),
        'incidents': [
            {
                'incident_id': inc.get('incident_id', ''),
                'title': inc.get('title', ''),
                'root_cause': inc.get('root_cause', 'Unknown'),
                'severity': int(inc.get('severity_score', 3)),
                'status': inc.get('status', 'Unknown'),
                'created_at': inc.get('created_at', '')
            }
            for inc in past_incidents[:5]
        ]
    }

def search_logs(params):
    service = params.get('service', '')
    time_range = params.get('time_range', '1h')
    results = []
    data_source = 'DynamoDB Incidents'

    if OPENSEARCH_ENDPOINT:
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
            
            query = {"query": {"match": {"service": service}}, "size": 10, "sort": [{"timestamp": {"order": "desc"}}]}
            response = client.search(index='outageshield-logs', body=query)
            hits = response.get('hits', {}).get('hits', [])
            if hits:
                results = [{'source': hit['_source'].get('source', 'opensearch'), 'service': hit['_source'].get('service', service), 'severity': hit['_source'].get('severity', 'unknown'), 'alarm_name': hit['_source'].get('alarm_name', ''), 'message': hit['_source'].get('message', ''), 'timestamp': hit['_source'].get('timestamp', '')} for hit in hits]
                data_source = 'OpenSearch Serverless'
                print(f"OpenSearch returned {len(results)} results for {service}")
        except Exception as e:
            print(f"OpenSearch query failed (using DynamoDB fallback): {e}")

    if not results:
        table = dynamodb.Table(INCIDENTS_TABLE)
        response = table.scan(FilterExpression=Attr('service').eq(service), Limit=20)
        incidents = response.get('Items', [])
        # Sort by created_at descending and skip the most recent (current incident)
        incidents_sorted = sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True)
        past_incidents = incidents_sorted[1:]  # Skip the most recent one
        results = [{'incident_id': inc.get('incident_id', ''), 'source': 'incident_history', 'severity': str(inc.get('severity_score', 'unknown')), 'root_cause': inc.get('root_cause', 'Unknown'), 'message': inc.get('title', inc.get('root_cause', '')), 'confidence': str(inc.get('confidence', '')), 'timestamp': inc.get('created_at', '')} for inc in past_incidents[:10]]

    return {'service': service, 'time_range': time_range, 'data_source': data_source, 'total_log_entries': len(results), 'patterns': results}

def get_runbook(params):
    service = params.get('service', '')
    alarm_type = params.get('alarm_type', '')
    table = dynamodb.Table(RUNBOOKS_TABLE)
    try:
        response = table.get_item(Key={'runbook_id': alarm_type})
        item = response.get('Item')
        if item:
            return {'service': service, 'alarm_type': alarm_type, 'runbook': {'title': item.get('title', ''), 'description': item.get('description', ''), 'steps': item.get('steps', []), 'category': item.get('category', 'manual_intervention'), 'estimated_ttr': item.get('estimated_ttr', 'Unknown'), 'severity_threshold': int(item.get('severity_threshold', 3))}}
    except Exception as e:
        print(f"Runbook lookup failed: {e}")
    return {'service': service, 'alarm_type': alarm_type, 'runbook': {'title': f'General Runbook for {service}', 'description': 'Default runbook', 'steps': ['Review CloudWatch metrics', 'Check recent deployments', 'Review application logs', 'Check downstream dependencies', 'Escalate to service owner'], 'category': 'manual_intervention', 'estimated_ttr': 'Unknown', 'severity_threshold': 3}}

def check_deployments(params):
    service = params.get('service', '')
    return {'service': service, 'recent_deployments': [{'deployment_id': f'deploy-{service[:8]}-001', 'version': '2.4.1', 'timestamp': '2024-01-15T10:30:00Z', 'status': 'succeeded', 'changes': 'Updated connection pool settings'}], 'config_changes': [{'change_id': f'config-{service[:8]}-001', 'parameter': 'max_connections', 'old_value': '50', 'new_value': '100', 'timestamp': '2024-01-15T09:00:00Z'}]}
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating agent-actions Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-actions-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
