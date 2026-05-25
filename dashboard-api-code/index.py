import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Dashboard API: Serves data for the Incident Command Dashboard.
    Routes: /incidents, /incidents/{id}, /risk, /postmortems, /events
    """
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')

    if path == '/incidents' and method == 'GET':
        return get_active_incidents()
    elif path.startswith('/incidents/') and method == 'GET':
        incident_id = path.split('/')[-1]
        return get_incident_detail(incident_id)
    elif path == '/risk' and method == 'GET':
        return get_risk_overview()
    elif path == '/postmortems' and method == 'GET':
        return get_postmortems()
    elif path == '/events' and method == 'GET':
        return get_events()
    else:
        return response(404, {'error': 'Not found'})

def get_active_incidents():
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.scan(
        FilterExpression='#s <> :resolved',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':resolved': 'resolved'}
    )
    incidents = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(
            FilterExpression='#s <> :resolved',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':resolved': 'resolved'},
            ExclusiveStartKey=result['LastEvaluatedKey']
        )
        incidents.extend(result.get('Items', []))
    incidents = sorted(incidents, key=lambda x: int(x.get('severity_score', 0)), reverse=True)
    return response(200, {'incidents': incidents, 'count': len(incidents)})

def get_incident_detail(incident_id):
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.get_item(Key={'incident_id': incident_id})
    item = result.get('Item')
    if item:
        return response(200, item)
    return response(404, {'error': 'Incident not found'})

def get_risk_overview():
    """Aggregate real service_risk_score and revenue_at_risk from incidents (scored by Bedrock AI)."""
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.scan(
        ProjectionExpression='service, severity_score, service_risk_score, business_impact_score, revenue_at_risk, created_at'
    )
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(
            ProjectionExpression='service, severity_score, service_risk_score, business_impact_score, revenue_at_risk, created_at',
            ExclusiveStartKey=result['LastEvaluatedKey']
        )
        items.extend(result.get('Items', []))

    svc_map = {}
    for item in items:
        svc = item.get('service', 'unknown')
        if svc not in svc_map:
            svc_map[svc] = {'scores': [], 'severities': [], 'count': 0, 'last_incident': '', 'revenue_values': []}
        svc_map[svc]['count'] += 1
        svc_map[svc]['scores'].append(int(item.get('service_risk_score', 50)))
        svc_map[svc]['severities'].append(int(item.get('severity_score', 3)))
        # Parse revenue_at_risk (e.g. "$5,000/hour") to numeric
        rev_str = item.get('revenue_at_risk', '0')
        rev_num = parse_revenue(rev_str)
        svc_map[svc]['revenue_values'].append(rev_num)
        ts = item.get('created_at', '')
        if ts > svc_map[svc]['last_incident']:
            svc_map[svc]['last_incident'] = ts

    services = []
    for svc, data in svc_map.items():
        avg_risk = sum(data['scores']) / len(data['scores']) if data['scores'] else 50
        max_sev = max(data['severities']) if data['severities'] else 3
        total_revenue = sum(data['revenue_values'])
        if avg_risk >= 85:
            risk_level = 'Critical'
        elif avg_risk >= 80:
            risk_level = 'High'
        elif avg_risk >= 75:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'
        services.append({
            'service': svc,
            'risk': risk_level,
            'risk_score': int(avg_risk),
            'revenue_at_risk': total_revenue,
            'activeSignals': data['count'],
            'max_severity': max_sev,
            'lastIncident': data['last_incident']
        })

    services.sort(key=lambda x: x['revenue_at_risk'], reverse=True)
    return response(200, {'services': services, 'last_calculated': ''})

def parse_revenue(rev_str):
    """Parse '$5,000/hour' or '$10,000/hour' to integer."""
    if not rev_str or rev_str == 'Unknown':
        return 0
    import re
    nums = re.findall(r'[\d,]+', str(rev_str))
    if nums:
        return int(nums[0].replace(',', ''))
    return 0

def get_postmortems():
    table = dynamodb.Table(os.environ.get('POSTMORTEMS_TABLE', 'outageshield-postmortems-dev'))
    result = table.scan()
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'])
        items.extend(result.get('Items', []))
    return response(200, {'postmortems': items, 'count': len(items)})

def get_events():
    table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'outageshield-events-dev'))
    result = table.scan()
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'])
        items.extend(result.get('Items', []))
    return response(200, {'events': items, 'count': len(items)})

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str)
    }
