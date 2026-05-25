"""Update the agent-actions Lambda to use real deployment data from DynamoDB."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'outageshield-events-dev')
RUNBOOKS_TABLE = os.environ.get('RUNBOOKS_TABLE', 'outageshield-runbooks-dev')
DEPLOYMENTS_TABLE = os.environ.get('DEPLOYMENTS_TABLE', 'outageshield-deployments-dev')
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
    incidents_sorted = sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True)
    past_incidents = incidents_sorted[1:]  # Skip the most recent one (current incident)
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
    """Query real deployment data from DynamoDB deployments table."""
    service = params.get('service', '')
    hours_back = int(params.get('hours_back', 24))
    
    table = dynamodb.Table(DEPLOYMENTS_TABLE)
    
    # Calculate time window - use a format that works with the stored timestamps
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=hours_back)).strftime('%Y-%m-%dT%H:%M:%S')
    
    print(f"Querying deployments for {service} since {cutoff}")
    
    deployments = []
    config_changes = []
    
    try:
        # Query by service using GSI
        response = table.query(
            IndexName='service-timestamp-index',
            KeyConditionExpression=Key('service').eq(service) & Key('timestamp').gte(cutoff),
            ScanIndexForward=False,  # Most recent first
            Limit=10
        )
        items = response.get('Items', [])
        
        print(f"Found {len(items)} items for {service}")
        
        for item in items:
            record_type = item.get('type', 'deployment')
            
            if record_type == 'config_change':
                config_changes.append({
                    'change_id': item.get('deployment_id', ''),
                    'parameter': item.get('parameter', ''),
                    'old_value': item.get('old_value', ''),
                    'new_value': item.get('new_value', ''),
                    'timestamp': item.get('timestamp', ''),
                    'service': item.get('service', service),
                    'changed_by': item.get('changed_by', 'unknown'),
                    'source': item.get('source', 'unknown'),
                    'reason': item.get('reason', '')
                })
            else:
                deployments.append({
                    'deployment_id': item.get('deployment_id', ''),
                    'version': item.get('version', ''),
                    'previous_version': item.get('previous_version', ''),
                    'timestamp': item.get('timestamp', ''),
                    'status': item.get('status', 'unknown'),
                    'changes': item.get('changes', ''),
                    'commit_sha': item.get('commit_sha', ''),
                    'deployed_by': item.get('deployed_by', 'unknown'),
                    'pipeline': item.get('pipeline', 'unknown'),
                    'environment': item.get('environment', 'unknown'),
                    'error_message': item.get('error_message', '')
                })
        
        print(f"Parsed {len(deployments)} deployments and {len(config_changes)} config changes for {service}")
        
    except Exception as e:
        print(f"Deployment query failed: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        'service': service,
        'time_window_hours': hours_back,
        'total_deployments': len(deployments),
        'total_config_changes': len(config_changes),
        'recent_deployments': deployments,
        'config_changes': config_changes,
        'data_source': 'DynamoDB (outageshield-deployments-dev)'
    }
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating agent-actions Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-actions-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")

# Add DEPLOYMENTS_TABLE env var
print("Adding DEPLOYMENTS_TABLE environment variable...")
try:
    config = lambda_client.get_function_configuration(FunctionName='outageshield-agent-actions-dev')
    env_vars = config.get('Environment', {}).get('Variables', {})
    env_vars['DEPLOYMENTS_TABLE'] = 'outageshield-deployments-dev'
    lambda_client.update_function_configuration(
        FunctionName='outageshield-agent-actions-dev',
        Environment={'Variables': env_vars}
    )
    print("✓ Environment variable added!")
except Exception as e:
    print(f"Note: Could not update env var: {e}")

print("\n✅ Agent actions Lambda updated to use real deployment data from DynamoDB!")
print("\nDeployment record schema:")
print("""
{
    "deployment_id": "deploy-checkout-001",      # Primary key
    "service": "checkout-service",               # GSI partition key
    "timestamp": "2024-01-15T10:30:00Z",         # GSI sort key
    "type": "deployment",                        # "deployment" or "config_change"
    "version": "2.4.1",
    "previous_version": "2.4.0",
    "status": "succeeded",
    "changes": "Updated connection pool settings",
    "commit_sha": "abc123",
    "deployed_by": "jenkins",
    "pipeline": "checkout-ci-cd",
    "environment": "production"
}

Config change record:
{
    "deployment_id": "config-checkout-001",
    "service": "checkout-service",
    "timestamp": "2024-01-15T09:00:00Z",
    "type": "config_change",
    "parameter": "max_connections",
    "old_value": "50",
    "new_value": "100",
    "changed_by": "terraform",
    "source": "aws-config"
}
""")
