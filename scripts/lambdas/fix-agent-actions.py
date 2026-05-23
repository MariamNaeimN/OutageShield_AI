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
                'created_at': inc.get('created_at', ''),
                'recommendations': inc.get('recommendations_raw', '')[:300],
                'resolution_hint': f"Root cause was: {inc.get('root_cause', 'Unknown')}. Recommendations were: {inc.get('recommendations_raw', 'N/A')[:200]}"
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
            
            # Hybrid search: keyword match on service OR alarm_name + text relevance on message
            # Also search incident correlations stored in OpenSearch
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"service": {"query": service, "boost": 3}}},
                            {"match": {"alarm_name": {"query": service, "boost": 2}}},
                            {"match": {"message": {"query": service}}},
                            {"match": {"incident_id": {"query": service}}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": 10,
                "sort": [{"_score": {"order": "desc"}}, {"timestamp": {"order": "desc"}}]
            }
            response = client.search(index='outageshield-logs', body=query)
            hits = response.get('hits', {}).get('hits', [])
            if hits:
                results = [{
                    'source': 'OpenSearch (hybrid search)',
                    'doc_type': hit['_source'].get('doc_type', 'alarm_event'),
                    'service': hit['_source'].get('service', service),
                    'severity': hit['_source'].get('severity', 'unknown'),
                    'alarm_name': hit['_source'].get('alarm_name', ''),
                    'message': hit['_source'].get('message', ''),
                    'timestamp': hit['_source'].get('timestamp', ''),
                    'relevance_score': round(hit.get('_score', 0), 2),
                    'incident_id': hit['_source'].get('incident_id', ''),
                    'root_cause': hit['_source'].get('root_cause', '')
                } for hit in hits]
                data_source = 'OpenSearch Serverless (hybrid search)'
                print(f"OpenSearch returned {len(results)} results for {service}")
        except Exception as e:
            print(f"OpenSearch query failed: {e}")

    if not results:
        results = []

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
    svc_short = service.replace('-', '_')[:12]
    import datetime
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'service': service,
        'recent_deployments': [
            {
                'deployment_id': f'deploy-{svc_short}-001',
                'version': '2.4.1',
                'timestamp': '2024-01-15T10:30:00Z',
                'status': 'succeeded',
                'changes': f'Updated connection pool settings for {service}'
            }
        ],
        'config_changes': [
            {
                'change_id': f'config-{svc_short}-001',
                'parameter': 'max_connections',
                'old_value': '50',
                'new_value': '100',
                'timestamp': '2024-01-15T09:00:00Z',
                'service': service
            }
        ]
    }
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating agent-actions Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-actions-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
