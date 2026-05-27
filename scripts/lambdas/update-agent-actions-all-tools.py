"""Update agent-actions Lambda to handle ALL 6 tools."""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
xray = boto3.client('xray')
config_client = boto3.client('config')

INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'outageshield-events-dev')
RUNBOOKS_TABLE = os.environ.get('RUNBOOKS_TABLE', 'outageshield-runbooks-dev')
DEPLOYMENTS_TABLE = os.environ.get('DEPLOYMENTS_TABLE', 'outageshield-deployments-dev')
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')

def lambda_handler(event, context):
    """Handle all 6 investigation tool API calls."""
    print(f"Agent action event: {json.dumps(event)}")
    
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    parameters = event.get('parameters', [])
    
    # Parse parameters
    params = {}
    for p in parameters:
        params[p['name']] = p['value']

    # Route to appropriate handler
    if api_path == '/search-incidents':
        result = search_incident_history(params)
    elif api_path == '/search-logs':
        result = search_logs(params)
    elif api_path == '/get-runbook':
        result = get_runbook(params)
    elif api_path == '/check-deployments':
        result = check_deployments(params)
    elif api_path == '/search-traces':
        result = search_traces(params)
    elif api_path == '/check-config-drift':
        result = check_config_drift(params)
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
    """Tool 1: Search past incidents for a service."""
    service = params.get('service', '')
    table = dynamodb.Table(INCIDENTS_TABLE)
    
    try:
        response = table.scan(FilterExpression=Attr('service').eq(service), Limit=20)
        incidents = response.get('Items', [])
        incidents_sorted = sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True)
        past_incidents = incidents_sorted[1:]  # Skip current incident
        
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
                    'recommendations': inc.get('recommendations_raw', '')[:300]
                }
                for inc in past_incidents[:5]
            ]
        }
    except Exception as e:
        print(f"Incident history search failed: {e}")
        return {'service': service, 'total_past_incidents': 0, 'incidents': [], 'error': str(e)}


def search_logs(params):
    """Tool 2: Search OpenSearch logs for error patterns."""
    service = params.get('service', '')
    time_range = params.get('time_range', '6h')
    results = []
    data_source = 'OpenSearch Serverless'

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
                            {"match": {"message": {"query": service}}}
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": 10,
                "sort": [{"_score": {"order": "desc"}}, {"timestamp": {"order": "desc"}}]
            }
            
            response = client.search(index='outageshield-logs', body=query)
            hits = response.get('hits', {}).get('hits', [])
            
            results = [{
                'source': 'OpenSearch',
                'service': hit['_source'].get('service', service),
                'severity': hit['_source'].get('severity', 'unknown'),
                'alarm_name': hit['_source'].get('alarm_name', ''),
                'message': hit['_source'].get('message', ''),
                'timestamp': hit['_source'].get('timestamp', ''),
                'relevance_score': round(hit.get('_score', 0), 2)
            } for hit in hits]
            
            print(f"OpenSearch returned {len(results)} results for {service}")
            
        except Exception as e:
            print(f"OpenSearch query failed: {e}")
            data_source = 'OpenSearch (connection failed)'

    return {
        'service': service,
        'time_range': time_range,
        'data_source': data_source,
        'total_log_entries': len(results),
        'patterns': results
    }


def get_runbook(params):
    """Tool 3: Get remediation runbook for alarm type."""
    service = params.get('service', '')
    alarm_type = params.get('alarm_type', '')
    table = dynamodb.Table(RUNBOOKS_TABLE)
    
    try:
        response = table.get_item(Key={'runbook_id': alarm_type})
        item = response.get('Item')
        
        if item:
            return {
                'service': service,
                'alarm_type': alarm_type,
                'found': True,
                'runbook': {
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'steps': item.get('steps', []),
                    'category': item.get('category', 'manual_intervention'),
                    'estimated_ttr': item.get('estimated_ttr', 'Unknown'),
                    'severity_threshold': int(item.get('severity_threshold', 3))
                }
            }
    except Exception as e:
        print(f"Runbook lookup failed: {e}")
    
    # Return default runbook
    return {
        'service': service,
        'alarm_type': alarm_type,
        'found': False,
        'runbook': {
            'title': f'General Troubleshooting for {alarm_type}',
            'description': 'Default troubleshooting runbook',
            'steps': [
                'Check CloudWatch metrics for anomalies',
                'Review recent deployments and config changes',
                'Check application logs for errors',
                'Verify downstream dependencies are healthy',
                'Escalate to service owner if unresolved'
            ],
            'category': 'manual_intervention',
            'estimated_ttr': '30-60 minutes',
            'severity_threshold': 3
        }
    }


def check_deployments(params):
    """Tool 4: Check recent deployments and config changes."""
    service = params.get('service', '')
    hours_back = int(params.get('hours_back', 24))
    
    table = dynamodb.Table(DEPLOYMENTS_TABLE)
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=hours_back)).strftime('%Y-%m-%dT%H:%M:%S')
    
    print(f"Querying deployments for {service} since {cutoff}")
    
    deployments = []
    config_changes = []
    
    try:
        response = table.query(
            IndexName='service-timestamp-index',
            KeyConditionExpression=Key('service').eq(service) & Key('timestamp').gte(cutoff),
            ScanIndexForward=False,
            Limit=10
        )
        items = response.get('Items', [])
        
        for item in items:
            record_type = item.get('type', 'deployment')
            
            if record_type == 'config_change':
                config_changes.append({
                    'change_id': item.get('deployment_id', ''),
                    'parameter': item.get('parameter', ''),
                    'old_value': item.get('old_value', ''),
                    'new_value': item.get('new_value', ''),
                    'timestamp': item.get('timestamp', ''),
                    'changed_by': item.get('changed_by', 'unknown'),
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
                    'deployed_by': item.get('deployed_by', 'unknown'),
                    'pipeline': item.get('pipeline', 'unknown')
                })
        
        print(f"Found {len(deployments)} deployments and {len(config_changes)} config changes")
        
    except Exception as e:
        print(f"Deployment query failed: {e}")
    
    return {
        'service': service,
        'time_window_hours': hours_back,
        'total_deployments': len(deployments),
        'total_config_changes': len(config_changes),
        'recent_deployments': deployments,
        'config_changes': config_changes,
        'data_source': 'DynamoDB (outageshield-deployments-dev)'
    }


def search_traces(params):
    """Tool 5: Search X-Ray traces for latency and errors."""
    service = params.get('service', '')
    time_range = params.get('time_range', '1h')
    
    # Parse time range
    hours = 1
    if 'h' in time_range:
        hours = int(time_range.replace('h', ''))
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    error_traces = []
    slow_traces = []
    service_stats = {}
    insights = []
    
    try:
        # Get trace summaries
        response = xray.get_trace_summaries(
            StartTime=start_time,
            EndTime=end_time,
            FilterExpression=f'service(id(name: "{service}"))',
            Sampling=False
        )
        
        traces = response.get('TraceSummaries', [])
        
        total_requests = len(traces)
        error_count = 0
        fault_count = 0
        total_duration = 0
        
        for trace in traces:
            duration_ms = trace.get('Duration', 0) * 1000
            total_duration += duration_ms
            
            if trace.get('HasError'):
                error_count += 1
                error_traces.append({
                    'trace_id': trace.get('Id', ''),
                    'duration_ms': round(duration_ms, 2),
                    'http_status': trace.get('Http', {}).get('HttpStatus', 0),
                    'error_message': 'Error detected in trace'
                })
            
            if trace.get('HasFault'):
                fault_count += 1
            
            if duration_ms > 1000:  # Slow trace > 1 second
                slow_traces.append({
                    'trace_id': trace.get('Id', ''),
                    'response_time_ms': round(duration_ms, 2)
                })
        
        avg_duration = total_duration / total_requests if total_requests > 0 else 0
        
        service_stats = {
            'name': service,
            'type': 'AWS::Lambda::Function',
            'total_requests': total_requests,
            'error_count': error_count,
            'fault_count': fault_count,
            'avg_response_time_ms': round(avg_duration, 2),
            'p99_latency_ms': round(max([t.get('Duration', 0) * 1000 for t in traces]) if traces else 0, 2)
        }
        
        # Get X-Ray insights
        try:
            insights_response = xray.get_insight_summaries(
                StartTime=start_time,
                EndTime=end_time,
                States=['ACTIVE']
            )
            for insight in insights_response.get('InsightSummaries', [])[:3]:
                insights.append({
                    'category': insight.get('Category', 'Unknown'),
                    'summary': insight.get('Summary', ''),
                    'state': insight.get('State', '')
                })
        except Exception as e:
            print(f"X-Ray insights failed: {e}")
        
    except Exception as e:
        print(f"X-Ray trace search failed: {e}")
        service_stats = {
            'name': service,
            'type': 'Unknown',
            'total_requests': 0,
            'error_count': 0,
            'fault_count': 0,
            'avg_response_time_ms': 0,
            'p99_latency_ms': 0,
            'error': str(e)
        }
    
    return {
        'service': service,
        'time_range': time_range,
        'service_stats': service_stats,
        'error_traces': error_traces[:5],
        'slow_traces': slow_traces[:5],
        'insights': insights,
        'data_source': 'AWS X-Ray'
    }


def check_config_drift(params):
    """Tool 6: Check AWS Config for configuration state and compliance."""
    service = params.get('service', '')
    
    summary = {
        'config_enabled': False,
        'total_non_compliant': 0,
        'total_changes': 0
    }
    non_compliant_resources = []
    recent_changes = []
    config_state = []
    
    try:
        # Check if Config is enabled
        recorders = config_client.describe_configuration_recorders()
        if recorders.get('ConfigurationRecorders'):
            summary['config_enabled'] = True
            
            # Get non-compliant resources
            try:
                compliance = config_client.get_compliance_summary_by_resource_type()
                for item in compliance.get('ComplianceSummariesByResourceType', []):
                    non_compliant = item.get('ComplianceSummary', {}).get('NonCompliantResourceCount', {})
                    if non_compliant.get('CappedCount', 0) > 0:
                        summary['total_non_compliant'] += non_compliant.get('CappedCount', 0)
            except Exception as e:
                print(f"Compliance check failed: {e}")
            
            # Get recent config changes
            try:
                history = config_client.get_resource_config_history(
                    resourceType='AWS::Lambda::Function',
                    resourceId=service,
                    limit=5
                )
                for item in history.get('configurationItems', []):
                    recent_changes.append({
                        'resource_type': item.get('resourceType', ''),
                        'resource_id': item.get('resourceId', ''),
                        'status': item.get('configurationItemStatus', ''),
                        'timestamp': item.get('configurationItemCaptureTime', '').isoformat() if item.get('configurationItemCaptureTime') else ''
                    })
                    summary['total_changes'] += 1
            except Exception as e:
                print(f"Config history failed: {e}")
    except Exception as e:
        print(f"AWS Config check failed: {e}")
    
    # If Config is not enabled, provide useful configuration state from other sources
    if not summary['config_enabled']:
        # Get Lambda configuration directly
        try:
            lambda_cfg_client = boto3.client('lambda')
            fn_config = lambda_cfg_client.get_function_configuration(FunctionName=service)
            
            memory = fn_config.get('MemorySize', 0)
            timeout = fn_config.get('Timeout', 0)
            runtime = fn_config.get('Runtime', 'N/A')
            tracing = fn_config.get('TracingConfig', {}).get('Mode', 'Disabled')
            vpc = fn_config.get('VpcConfig', {}).get('VpcId', '')
            env_count = len(fn_config.get('Environment', {}).get('Variables', {}))
            last_modified = fn_config.get('LastModified', 'N/A')
            
            config_state = [
                {'setting': 'Memory', 'value': f'{memory} MB', 'status': 'OK' if memory >= 256 else 'Low'},
                {'setting': 'Timeout', 'value': f'{timeout}s', 'status': 'OK' if timeout >= 30 else 'Low'},
                {'setting': 'Runtime', 'value': runtime, 'status': 'OK'},
                {'setting': 'X-Ray', 'value': tracing, 'status': 'OK' if tracing == 'Active' else 'Disabled'},
                {'setting': 'VPC', 'value': 'Yes' if vpc else 'No', 'status': 'OK'},
                {'setting': 'Env Vars', 'value': str(env_count), 'status': 'OK'},
                {'setting': 'Modified', 'value': last_modified[:19] if len(last_modified) > 19 else last_modified, 'status': 'Info'}
            ]
            
            summary['lambda_config_retrieved'] = True
            summary['function_name'] = service
            summary['memory_mb'] = memory
            summary['timeout_sec'] = timeout
            summary['runtime'] = runtime
            summary['xray_enabled'] = tracing == 'Active'
            
        except Exception as e:
            print(f"Lambda config retrieval failed: {e}")
            # Service is not a Lambda - provide service-specific config recommendations
            config_state = [
                {'setting': 'Auto-Scaling', 'value': 'Verify enabled', 'status': 'Check'},
                {'setting': 'Health Checks', 'value': 'Verify configured', 'status': 'Check'},
                {'setting': 'Connection Pool', 'value': 'Review limits', 'status': 'Check'},
                {'setting': 'Timeouts', 'value': 'Review settings', 'status': 'Check'},
                {'setting': 'Resource Limits', 'value': 'Check CPU/Memory', 'status': 'Check'}
            ]
            summary['service_type'] = 'application'
            summary['note'] = f'{service} is not a Lambda - showing general config checks'
    
    return {
        'service': service,
        'summary': summary,
        'configuration_state': config_state,
        'non_compliant_resources': non_compliant_resources,
        'recent_changes': recent_changes,
        'data_source': 'AWS Config' if summary['config_enabled'] else 'Service Config'
    }
'''

# Create zip file
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
buf.seek(0)

print("Updating agent-actions Lambda with ALL 6 tools...")
r = lambda_client.update_function_code(
    FunctionName='outageshield-agent-actions-dev',
    ZipFile=buf.read()
)
print(f"✓ Updated! Last modified: {r['LastModified']}")

# Update environment variables
import time
time.sleep(3)

print("\nUpdating environment variables...")
try:
    config = lambda_client.get_function_configuration(FunctionName='outageshield-agent-actions-dev')
    env_vars = config.get('Environment', {}).get('Variables', {})
    env_vars['DEPLOYMENTS_TABLE'] = 'outageshield-deployments-dev'
    env_vars['RUNBOOKS_TABLE'] = 'outageshield-runbooks-dev'
    env_vars['INCIDENTS_TABLE'] = 'outageshield-incidents-dev'
    
    lambda_client.update_function_configuration(
        FunctionName='outageshield-agent-actions-dev',
        Environment={'Variables': env_vars}
    )
    print("✓ Environment variables updated!")
except Exception as e:
    print(f"Note: {e}")

print("\n" + "=" * 60)
print("AGENT ACTIONS LAMBDA - ALL 6 TOOLS")
print("=" * 60)
print("API Endpoints:")
print("  1. /search-incidents   - Search past incidents (DynamoDB)")
print("  2. /search-logs        - Search logs (OpenSearch)")
print("  3. /get-runbook        - Get runbook (DynamoDB)")
print("  4. /check-deployments  - Check deployments (DynamoDB)")
print("  5. /search-traces      - Search X-Ray traces (X-Ray API)")
print("  6. /check-config-drift - Check AWS Config (Config API)")
print("=" * 60)
