"""
Add X-Ray and Config tools to the agent-actions Lambda.
This extends the Bedrock Agent with 2 new investigation tools:
- searchTraces: Query X-Ray for latency/error traces
- checkConfigDrift: Check AWS Config for compliance issues
"""
import boto3
import zipfile
import io
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')

LAMBDA_CODE = r'''
import json
import boto3
import os
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Attr, Key

dynamodb = boto3.resource('dynamodb')
xray = boto3.client('xray')
config_client = boto3.client('config')

INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'outageshield-events-dev')
RUNBOOKS_TABLE = os.environ.get('RUNBOOKS_TABLE', 'outageshield-runbooks-dev')
DEPLOYMENTS_TABLE = os.environ.get('DEPLOYMENTS_TABLE', 'outageshield-deployments-dev')
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')

def lambda_handler(event, context):
    """
    Bedrock Agent Action Group handler.
    Routes to the appropriate tool based on the action group and API path.
    Now includes 6 tools: 4 original + X-Ray + Config
    """
    print(f"Agent action event: {json.dumps(event)}")

    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    parameters = event.get('parameters', [])

    # Extract parameters into a dict
    params = {}
    for p in parameters:
        params[p['name']] = p['value']

    # Route to appropriate tool
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

    # Return in Bedrock Agent expected format
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
    """Search past incidents for the same service."""
    service = params.get('service', '')
    current_incident_id = params.get('current_incident_id', '')
    
    table = dynamodb.Table(INCIDENTS_TABLE)
    response = table.scan(
        FilterExpression=Attr('service').eq(service),
        Limit=20
    )
    incidents = response.get('Items', [])
    
    # Sort by created_at descending and exclude current incident
    incidents_sorted = sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True)
    past_incidents = [i for i in incidents_sorted if i.get('incident_id') != current_incident_id][:5]

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
            for inc in past_incidents
        ]
    }


def search_logs(params):
    """Search OpenSearch for log patterns."""
    service = params.get('service', '')
    time_range = params.get('time_range', '6h')
    
    results = []
    data_source = 'No data'

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
            
            if hits:
                results = [{
                    'alarm_name': hit['_source'].get('alarm_name', ''),
                    'severity': hit['_source'].get('severity', 'unknown'),
                    'message': hit['_source'].get('message', ''),
                    'timestamp': hit['_source'].get('timestamp', ''),
                    'root_cause': hit['_source'].get('root_cause', '')
                } for hit in hits]
                data_source = 'OpenSearch'
                print(f"OpenSearch returned {len(results)} results for {service}")
        except Exception as e:
            print(f"OpenSearch query failed: {e}")
            data_source = f'OpenSearch error: {str(e)[:50]}'

    return {
        'service': service,
        'time_range': time_range,
        'data_source': data_source,
        'total_log_entries': len(results),
        'patterns': results
    }


def get_runbook(params):
    """Look up remediation runbook from DynamoDB."""
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
                    'estimated_ttr': item.get('estimated_ttr', 'Unknown')
                }
            }
    except Exception as e:
        print(f"Runbook lookup failed: {e}")

    return {
        'service': service,
        'alarm_type': alarm_type,
        'found': False,
        'runbook': None
    }


def check_deployments(params):
    """Check recent deployments from DynamoDB."""
    service = params.get('service', '')
    
    table = dynamodb.Table(DEPLOYMENTS_TABLE)
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
    
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
                    'parameter': item.get('parameter', ''),
                    'old_value': item.get('old_value', ''),
                    'new_value': item.get('new_value', ''),
                    'timestamp': item.get('timestamp', ''),
                    'reason': item.get('reason', '')
                })
            else:
                deployments.append({
                    'deployment_id': item.get('deployment_id', ''),
                    'version': item.get('version', ''),
                    'timestamp': item.get('timestamp', ''),
                    'status': item.get('status', 'unknown'),
                    'changes': item.get('changes', '')
                })
    except Exception as e:
        print(f"Deployment query failed: {e}")

    return {
        'service': service,
        'total_deployments': len(deployments),
        'total_config_changes': len(config_changes),
        'deployments': deployments,
        'config_changes': config_changes
    }


def generate_sample_xray_data(service):
    """Generate realistic sample X-Ray data for demo purposes."""
    import random
    import hashlib
    
    # Generate deterministic but realistic trace IDs based on service name
    seed = hashlib.md5(service.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc)
    
    # Sample error traces - realistic scenarios
    error_traces = [
        {
            'trace_id': f'1-{seed}01-{seed}abcdef123456789012',
            'duration_ms': 2340,
            'has_error': True,
            'has_fault': False,
            'http_status': 500,
            'http_url': f'/api/{service}/process',
            'error_type': 'Internal Server Error - Database connection timeout'
        },
        {
            'trace_id': f'1-{seed}02-{seed}fedcba987654321098',
            'duration_ms': 1850,
            'has_error': True,
            'has_fault': True,
            'http_status': 503,
            'http_url': f'/api/{service}/health',
            'error_type': 'Service Unavailable - Downstream dependency failure'
        },
        {
            'trace_id': f'1-{seed}03-{seed}112233445566778899',
            'duration_ms': 3200,
            'has_error': True,
            'has_fault': False,
            'http_status': 504,
            'http_url': f'/api/{service}/query',
            'error_type': 'Gateway Timeout - Lambda cold start exceeded'
        }
    ]
    
    # Sample slow traces - realistic latency issues
    slow_traces = [
        {
            'trace_id': f'1-{seed}04-{seed}aabbccdd11223344',
            'duration_ms': 4500,
            'response_time_ms': 4200,
            'http_url': f'/api/{service}/list',
            'bottleneck': 'DynamoDB scan operation'
        },
        {
            'trace_id': f'1-{seed}05-{seed}55667788aabbccdd',
            'duration_ms': 3800,
            'response_time_ms': 3500,
            'http_url': f'/api/{service}/export',
            'bottleneck': 'S3 multipart upload'
        },
        {
            'trace_id': f'1-{seed}06-{seed}eeff00112233aabb',
            'duration_ms': 2900,
            'response_time_ms': 2700,
            'http_url': f'/api/{service}/aggregate',
            'bottleneck': 'OpenSearch aggregation query'
        }
    ]
    
    # Service statistics
    service_stats = {
        'name': service,
        'type': 'AWS::Lambda::Function',
        'total_requests': 15420,
        'ok_count': 14850,
        'error_count': 420,
        'fault_count': 150,
        'avg_response_time_ms': 245,
        'error_rate_percent': 2.7,
        'p99_latency_ms': 1850
    }
    
    # X-Ray Insights - realistic anomaly detection
    insights = [
        {
            'insight_id': f'insight-{seed}-001',
            'category': 'FAULT',
            'state': 'ACTIVE',
            'summary': f'Increased error rate detected in {service}. Error rate increased from 0.5% to 2.7% in the last hour. Root cause appears to be database connection pool exhaustion.',
            'root_cause_service': f'{service}-database',
            'impact': 'HIGH'
        },
        {
            'insight_id': f'insight-{seed}-002',
            'category': 'LATENCY',
            'state': 'ACTIVE',
            'summary': f'Response time anomaly detected. P99 latency increased from 500ms to 1850ms. Correlated with increased DynamoDB read capacity consumption.',
            'root_cause_service': f'{service}-dynamodb',
            'impact': 'MEDIUM'
        }
    ]
    
    return {
        'error_traces': error_traces,
        'slow_traces': slow_traces,
        'service_stats': service_stats,
        'insights': insights
    }


def search_traces(params):
    """Search X-Ray traces for latency and error patterns."""
    service = params.get('service', '')
    time_range = params.get('time_range', '1h')
    
    # Parse time range
    hours = int(time_range.replace('h', '')) if 'h' in time_range else 1
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    
    results = {
        'service': service,
        'time_range': time_range,
        'error_traces': [],
        'slow_traces': [],
        'service_stats': {},
        'insights': [],
        'data_source': 'AWS X-Ray'
    }
    
    has_real_data = False
    
    try:
        # Build filter expression for the service
        filter_expr = f'service(id(name: "{service}"))'
        
        # Get error traces
        try:
            error_response = xray.get_trace_summaries(
                StartTime=start_time,
                EndTime=end_time,
                FilterExpression=f'{filter_expr} AND error',
                Sampling=True
            )
            
            for t in error_response.get('TraceSummaries', [])[:5]:
                has_real_data = True
                results['error_traces'].append({
                    'trace_id': t.get('Id', ''),
                    'duration_ms': int(t.get('Duration', 0) * 1000),
                    'has_error': t.get('HasError', False),
                    'has_fault': t.get('HasFault', False),
                    'http_status': t.get('Http', {}).get('HttpStatus', 0),
                    'http_url': t.get('Http', {}).get('HttpURL', '')[:100]
                })
        except Exception as e:
            print(f"Error traces query failed: {e}")
        
        # Get slow traces (>1s)
        try:
            slow_response = xray.get_trace_summaries(
                StartTime=start_time,
                EndTime=end_time,
                FilterExpression=f'{filter_expr} AND responsetime > 1',
                Sampling=True
            )
            
            for t in slow_response.get('TraceSummaries', [])[:5]:
                has_real_data = True
                results['slow_traces'].append({
                    'trace_id': t.get('Id', ''),
                    'duration_ms': int(t.get('Duration', 0) * 1000),
                    'response_time_ms': int(t.get('ResponseTime', 0) * 1000),
                    'http_url': t.get('Http', {}).get('HttpURL', '')[:100]
                })
        except Exception as e:
            print(f"Slow traces query failed: {e}")
        
        # Get service graph stats
        try:
            graph_response = xray.get_service_graph(
                StartTime=start_time,
                EndTime=end_time
            )
            
            for svc in graph_response.get('Services', []):
                if service.lower() in svc.get('Name', '').lower():
                    has_real_data = True
                    summary = svc.get('SummaryStatistics', {})
                    total = summary.get('TotalCount', 0)
                    results['service_stats'] = {
                        'name': svc.get('Name', ''),
                        'type': svc.get('Type', ''),
                        'total_requests': total,
                        'ok_count': summary.get('OkCount', 0),
                        'error_count': summary.get('ErrorStatistics', {}).get('TotalCount', 0),
                        'fault_count': summary.get('FaultStatistics', {}).get('TotalCount', 0),
                        'avg_response_time_ms': int((summary.get('TotalResponseTime', 0) / max(total, 1)) * 1000)
                    }
                    break
        except Exception as e:
            print(f"Service graph query failed: {e}")
        
        # Get X-Ray Insights
        try:
            insights_response = xray.get_insight_summaries(
                StartTime=start_time,
                EndTime=end_time,
                States=['ACTIVE']
            )
            
            for i in insights_response.get('InsightSummaries', [])[:3]:
                has_real_data = True
                results['insights'].append({
                    'insight_id': i.get('InsightId', ''),
                    'category': i.get('Categories', ['Unknown'])[0] if i.get('Categories') else 'Unknown',
                    'state': i.get('State', ''),
                    'summary': i.get('Summary', '')[:200],
                    'root_cause_service': i.get('RootCauseServiceId', {}).get('Name', '')
                })
        except Exception as e:
            print(f"Insights query failed: {e}")
        
        # If no real data found, use sample data for demo
        if not has_real_data:
            print(f"No real X-Ray data found for {service}, using sample data for demo")
            sample_data = generate_sample_xray_data(service)
            results['error_traces'] = sample_data['error_traces']
            results['slow_traces'] = sample_data['slow_traces']
            results['service_stats'] = sample_data['service_stats']
            results['insights'] = sample_data['insights']
            results['data_source'] = 'Sample Data (X-Ray not enabled for this service)'
        
        results['summary'] = {
            'total_error_traces': len(results['error_traces']),
            'total_slow_traces': len(results['slow_traces']),
            'total_insights': len(results['insights']),
            'service_found': bool(results['service_stats']),
            'is_sample_data': not has_real_data
        }
        
    except Exception as e:
        print(f"X-Ray search failed: {e}, using sample data")
        # Use sample data on any failure
        sample_data = generate_sample_xray_data(service)
        results['error_traces'] = sample_data['error_traces']
        results['slow_traces'] = sample_data['slow_traces']
        results['service_stats'] = sample_data['service_stats']
        results['insights'] = sample_data['insights']
        results['data_source'] = 'Sample Data (X-Ray query failed)'
        results['summary'] = {
            'total_error_traces': len(results['error_traces']),
            'total_slow_traces': len(results['slow_traces']),
            'total_insights': len(results['insights']),
            'service_found': True,
            'is_sample_data': True
        }
    
    return results


def generate_sample_config_data(service):
    """Generate realistic sample AWS Config data for demo purposes."""
    import hashlib
    
    seed = hashlib.md5(service.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc)
    
    # Sample non-compliant resources - realistic compliance issues
    non_compliant_resources = [
        {
            'resource_id': f'{service}-lambda-function',
            'resource_type': 'AWS::Lambda::Function',
            'compliance_status': 'NON_COMPLIANT',
            'violations': [
                {
                    'rule_name': 'lambda-function-public-access-prohibited',
                    'annotation': 'Lambda function has resource-based policy allowing public access'
                },
                {
                    'rule_name': 'lambda-inside-vpc',
                    'annotation': 'Lambda function is not configured to run inside a VPC'
                }
            ]
        },
        {
            'resource_id': f'{service}-security-group',
            'resource_type': 'AWS::EC2::SecurityGroup',
            'compliance_status': 'NON_COMPLIANT',
            'violations': [
                {
                    'rule_name': 'restricted-ssh',
                    'annotation': 'Security group allows SSH access from 0.0.0.0/0'
                }
            ]
        },
        {
            'resource_id': f'{service}-dynamodb-table',
            'resource_type': 'AWS::DynamoDB::Table',
            'compliance_status': 'NON_COMPLIANT',
            'violations': [
                {
                    'rule_name': 'dynamodb-pitr-enabled',
                    'annotation': 'DynamoDB table does not have point-in-time recovery enabled'
                },
                {
                    'rule_name': 'dynamodb-table-encrypted-kms',
                    'annotation': 'DynamoDB table is not encrypted with customer managed KMS key'
                }
            ]
        },
        {
            'resource_id': f'{service}-s3-bucket',
            'resource_type': 'AWS::S3::Bucket',
            'compliance_status': 'NON_COMPLIANT',
            'violations': [
                {
                    'rule_name': 's3-bucket-ssl-requests-only',
                    'annotation': 'S3 bucket policy does not enforce SSL-only access'
                }
            ]
        }
    ]
    
    # Sample recent configuration changes - realistic drift scenarios
    recent_changes = [
        {
            'resource_id': f'{service}-lambda-function',
            'resource_type': 'AWS::Lambda::Function',
            'capture_time': (now - timedelta(hours=2)).isoformat(),
            'status': 'ResourceDiscovered',
            'change_type': 'Memory increased from 512MB to 1024MB',
            'changed_by': 'deployment-pipeline'
        },
        {
            'resource_id': f'{service}-security-group',
            'resource_type': 'AWS::EC2::SecurityGroup',
            'capture_time': (now - timedelta(hours=4)).isoformat(),
            'status': 'ResourceDiscovered',
            'change_type': 'Inbound rule added: port 443 from 0.0.0.0/0',
            'changed_by': 'manual-console-change'
        },
        {
            'resource_id': f'{service}-iam-role',
            'resource_type': 'AWS::IAM::Role',
            'capture_time': (now - timedelta(hours=6)).isoformat(),
            'status': 'ResourceDiscovered',
            'change_type': 'Policy attached: AmazonS3FullAccess',
            'changed_by': 'terraform-apply'
        },
        {
            'resource_id': f'{service}-rds-instance',
            'resource_type': 'AWS::RDS::DBInstance',
            'capture_time': (now - timedelta(hours=8)).isoformat(),
            'status': 'ResourceDiscovered',
            'change_type': 'Parameter group changed: max_connections increased',
            'changed_by': 'dba-team'
        },
        {
            'resource_id': f'{service}-api-gateway',
            'resource_type': 'AWS::ApiGateway::RestApi',
            'capture_time': (now - timedelta(hours=12)).isoformat(),
            'status': 'ResourceDiscovered',
            'change_type': 'Throttling limits modified: 10000 req/s to 5000 req/s',
            'changed_by': 'cost-optimization-script'
        }
    ]
    
    return {
        'non_compliant_resources': non_compliant_resources,
        'recent_changes': recent_changes
    }


def check_config_drift(params):
    """Check AWS Config for compliance issues and configuration drift."""
    service = params.get('service', '')
    
    results = {
        'service': service,
        'non_compliant_resources': [],
        'recent_changes': [],
        'compliance_summary': {},
        'data_source': 'AWS Config'
    }
    
    has_real_data = False
    config_enabled = False
    
    try:
        # Check if Config is enabled
        recorder_status = config_client.describe_configuration_recorder_status()
        recorders = recorder_status.get('ConfigurationRecordersStatus', [])
        config_enabled = any(r.get('recording', False) for r in recorders)
        
        if config_enabled:
            # Get non-compliant resources
            try:
                compliance_response = config_client.describe_compliance_by_resource(
                    ComplianceTypes=['NON_COMPLIANT'],
                    Limit=25
                )
                
                for resource in compliance_response.get('ComplianceByResources', []):
                    resource_id = resource.get('ResourceId', '')
                    
                    # Filter by service name if provided
                    if not service or service.lower() in resource_id.lower():
                        has_real_data = True
                        results['non_compliant_resources'].append({
                            'resource_id': resource_id,
                            'resource_type': resource.get('ResourceType', ''),
                            'compliance_status': 'NON_COMPLIANT'
                        })
            except Exception as e:
                print(f"Compliance query failed: {e}")
            
            # Get compliance details for top non-compliant resources
            for resource in results['non_compliant_resources'][:3]:
                try:
                    details = config_client.get_compliance_details_by_resource(
                        ResourceType=resource['resource_type'],
                        ResourceId=resource['resource_id'],
                        ComplianceTypes=['NON_COMPLIANT']
                    )
                    
                    violations = []
                    for e in details.get('EvaluationResults', [])[:2]:
                        violations.append({
                            'rule_name': e.get('EvaluationResultIdentifier', {}).get('EvaluationResultQualifier', {}).get('ConfigRuleName', ''),
                            'annotation': e.get('Annotation', '')[:100]
                        })
                    resource['violations'] = violations
                except Exception as e:
                    print(f"Details query failed: {e}")
            
            # Get recent configuration changes
            try:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                
                if service:
                    query = f"SELECT resourceId, resourceType, configurationItemCaptureTime, configurationItemStatus WHERE resourceId LIKE '%{service}%' LIMIT 10"
                else:
                    query = "SELECT resourceId, resourceType, configurationItemCaptureTime, configurationItemStatus LIMIT 10"
                
                query_response = config_client.select_resource_config(Expression=query)
                
                for result in query_response.get('Results', []):
                    has_real_data = True
                    item = json.loads(result)
                    results['recent_changes'].append({
                        'resource_id': item.get('resourceId', ''),
                        'resource_type': item.get('resourceType', ''),
                        'capture_time': item.get('configurationItemCaptureTime', ''),
                        'status': item.get('configurationItemStatus', '')
                    })
            except Exception as e:
                print(f"Config changes query failed: {e}")
        
        # If no real data found or Config not enabled, use sample data for demo
        if not has_real_data:
            print(f"No real Config data found for {service}, using sample data for demo")
            sample_data = generate_sample_config_data(service)
            results['non_compliant_resources'] = sample_data['non_compliant_resources']
            results['recent_changes'] = sample_data['recent_changes']
            if config_enabled:
                results['data_source'] = 'Sample Data (No Config data for this service)'
            else:
                results['data_source'] = 'Sample Data (AWS Config not enabled)'
        
        results['summary'] = {
            'config_enabled': config_enabled,
            'total_non_compliant': len(results['non_compliant_resources']),
            'total_changes': len(results['recent_changes']),
            'is_sample_data': not has_real_data
        }
        
    except Exception as e:
        print(f"Config drift check failed: {e}, using sample data")
        # Use sample data on any failure
        sample_data = generate_sample_config_data(service)
        results['non_compliant_resources'] = sample_data['non_compliant_resources']
        results['recent_changes'] = sample_data['recent_changes']
        results['data_source'] = 'Sample Data (AWS Config query failed)'
        results['summary'] = {
            'config_enabled': False,
            'total_non_compliant': len(results['non_compliant_resources']),
            'total_changes': len(results['recent_changes']),
            'is_sample_data': True
        }
    
    return results
'''

# Create zip file
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', LAMBDA_CODE.strip())
zip_buffer.seek(0)

print("=" * 60)
print("Adding X-Ray and Config Tools to Agent Actions Lambda")
print("=" * 60)
print()
print("New tools added:")
print("  1. searchTraces - Query X-Ray for error/latency traces")
print("  2. checkConfigDrift - Check AWS Config for compliance issues")
print()
print("Existing tools preserved:")
print("  - searchIncidentHistory")
print("  - searchLogs")
print("  - getRunbook")
print("  - checkDeployments")
print()

# Update Lambda code
response = lambda_client.update_function_code(
    FunctionName='outageshield-agent-actions-dev',
    ZipFile=zip_buffer.read()
)
print(f"✓ Lambda code updated! Last modified: {response['LastModified']}")

# Add X-Ray and Config permissions to the Lambda role
iam = boto3.client('iam')
role_name = 'outageshield-agent-action-role-dev'

xray_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "xray:GetTraceSummaries",
                "xray:BatchGetTraces",
                "xray:GetServiceGraph",
                "xray:GetInsightSummaries"
            ],
            "Resource": "*"
        }
    ]
}

config_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "config:DescribeComplianceByResource",
                "config:GetComplianceDetailsByResource",
                "config:SelectResourceConfig",
                "config:DescribeConfigurationRecorderStatus"
            ],
            "Resource": "*"
        }
    ]
}

try:
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName='XRayReadAccess',
        PolicyDocument=json.dumps(xray_policy)
    )
    print("✓ X-Ray permissions added to Lambda role")
except Exception as e:
    print(f"⚠ X-Ray permissions: {e}")

try:
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName='ConfigReadAccess',
        PolicyDocument=json.dumps(config_policy)
    )
    print("✓ Config permissions added to Lambda role")
except Exception as e:
    print(f"⚠ Config permissions: {e}")

print()
print("=" * 60)
print("IMPORTANT: Update Bedrock Agent API Schema")
print("=" * 60)
print()
print("To enable the new tools, update the Bedrock Agent's OpenAPI schema")
print("to include /search-traces and /check-config-drift endpoints.")
print()
print("Run: python scripts/lambdas/update-agent-schema.py")
