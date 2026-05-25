"""
Add ServiceNow integration to the ticket-integrator Lambda.
Supports both Jira and ServiceNow based on configuration.
"""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')

LAMBDA_CODE = r'''
import json
import boto3
import os
import urllib.request
import urllib.error
import base64
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
sm = boto3.client('secretsmanager')

INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
JIRA_SECRET = os.environ.get('JIRA_SECRET', 'outageshield/jira-credentials')
SERVICENOW_SECRET = os.environ.get('SERVICENOW_SECRET', 'outageshield/servicenow-credentials')
TICKET_SYSTEM = os.environ.get('TICKET_SYSTEM', 'jira')  # 'jira' or 'servicenow' or 'both'
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://d2k1km1tzlio49.cloudfront.net')


def lambda_handler(event, context):
    """
    Create tickets in Jira and/or ServiceNow based on configuration.
    """
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    service = signal.get('service', 'unknown')

    step2 = event.get('step2', {})
    step3 = event.get('step3', {})
    severity = step2.get('severity_score', 4)
    biz_impact = step2.get('business_impact_score', 5)
    revenue = step2.get('revenue_at_risk', 'Unknown')
    affected_users = step2.get('affected_users', 0)
    sla_status = step2.get('sla_status', 'Unknown')

    root_causes = step3.get('root_causes', [])
    top_rc = root_causes[0].get('description', 'Under investigation') if root_causes else 'Under investigation'
    confidence = root_causes[0].get('confidence', 0) if root_causes else 0

    alarm_name = signal.get('alarm_name', f'Incident on {service}')
    reason = signal.get('reason', 'Anomaly detected')

    results = {
        'statusCode': 200,
        'tickets': [],
        'severity': severity,
        'root_cause': top_rc
    }

    # Create Jira ticket
    if TICKET_SYSTEM in ['jira', 'both']:
        jira_result = create_jira_ticket(
            incident_id, service, severity, biz_impact, revenue,
            affected_users, sla_status, top_rc, confidence, alarm_name, reason
        )
        results['tickets'].append(jira_result)
        if jira_result.get('success'):
            results['ticket_id'] = jira_result['ticket_id']
            results['ticket_url'] = jira_result['ticket_url']

    # Create ServiceNow incident
    if TICKET_SYSTEM in ['servicenow', 'both']:
        snow_result = create_servicenow_incident(
            incident_id, service, severity, biz_impact, revenue,
            affected_users, sla_status, top_rc, confidence, alarm_name, reason
        )
        results['tickets'].append(snow_result)
        if snow_result.get('success') and 'ticket_id' not in results:
            results['ticket_id'] = snow_result['ticket_id']
            results['ticket_url'] = snow_result['ticket_url']

    # Store in DynamoDB
    store_ticket_info(incident_id, results)

    return results


def create_jira_ticket(incident_id, service, severity, biz_impact, revenue,
                       affected_users, sla_status, top_rc, confidence, alarm_name, reason):
    """Create a Jira ticket."""
    try:
        secret = sm.get_secret_value(SecretId=JIRA_SECRET)
        creds = json.loads(secret['SecretString'])
        jira_url = creds['jira_url']
        project_key = creds['project_key']
        email = creds['email']
        api_token = creds['api_token']
    except Exception as e:
        print(f"Failed to get Jira credentials: {e}")
        return {'system': 'Jira', 'success': False, 'error': str(e)[:100]}

    summary = f"[OutageShield] SEV-{severity} | {service} | {alarm_name}"
    dashboard_link = f"{DASHBOARD_URL}/incidents/{incident_id}"

    desc_content = [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Incident Details"}]},
        {"type": "table", "content": [
            {"type": "tableRow", "content": [
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Field"}]}]},
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Value"}]}]}
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Incident ID"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": incident_id}]}]}
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Service"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": service}]}]}
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Severity"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": f"SEV-{severity}"}]}]}
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Revenue at Risk"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(revenue)}]}]}
            ]},
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Affected Users"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(affected_users)}]}]}
            ]}
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Root Cause Analysis"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": f"Confidence: {confidence}%", "marks": [{"type": "strong"}]}]},
        {"type": "paragraph", "content": [{"type": "text", "text": top_rc}]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Dashboard"}]},
        {"type": "paragraph", "content": [
            {"type": "text", "text": "View in OutageShield: "},
            {"type": "text", "text": dashboard_link, "marks": [{"type": "link", "attrs": {"href": dashboard_link}}]}
        ]}
    ]

    priority_map = {5: 'Highest', 4: 'High', 3: 'Medium', 2: 'Low', 1: 'Lowest'}
    priority = priority_map.get(severity, 'High')

    issue_data = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary[:255],
            "description": {"type": "doc", "version": 1, "content": desc_content},
            "issuetype": {"name": "Task"},
            "priority": {"name": priority}
        }
    }

    try:
        url = f"{jira_url}/rest/api/3/issue"
        data = json.dumps(issue_data).encode('utf-8')
        auth_bytes = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Basic {auth_bytes}')
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        ticket_id = result.get('key', 'UNKNOWN')
        ticket_url = f"{jira_url}/browse/{ticket_id}"
        print(f"Jira ticket created: {ticket_id}")
        return {
            'system': 'Jira',
            'success': True,
            'ticket_id': ticket_id,
            'ticket_url': ticket_url
        }
    except Exception as e:
        print(f"Jira error: {e}")
        return {'system': 'Jira', 'success': False, 'error': str(e)[:100]}


def create_servicenow_incident(incident_id, service, severity, biz_impact, revenue,
                                affected_users, sla_status, top_rc, confidence, alarm_name, reason):
    """Create a ServiceNow incident."""
    try:
        secret = sm.get_secret_value(SecretId=SERVICENOW_SECRET)
        creds = json.loads(secret['SecretString'])
        instance_url = creds['instance_url']  # e.g., https://dev12345.service-now.com
        username = creds['username']
        password = creds['password']
        assignment_group = creds.get('assignment_group', '')
        caller_id = creds.get('caller_id', '')
    except Exception as e:
        print(f"Failed to get ServiceNow credentials: {e}")
        return {'system': 'ServiceNow', 'success': False, 'error': str(e)[:100]}

    # Map severity to ServiceNow impact/urgency
    # ServiceNow: 1=High, 2=Medium, 3=Low
    severity_map = {5: 1, 4: 1, 3: 2, 2: 3, 1: 3}
    snow_impact = severity_map.get(severity, 2)
    snow_urgency = severity_map.get(severity, 2)

    dashboard_link = f"{DASHBOARD_URL}/incidents/{incident_id}"

    short_description = f"[OutageShield] SEV-{severity} | {service} | {alarm_name}"

    work_notes = f"""OutageShield AI - Automated Incident Detection
==================================================

Incident ID: {incident_id}
Service: {service}
Severity: SEV-{severity}
Business Impact: {biz_impact}/10
Revenue at Risk: {revenue}
Affected Users: {affected_users}
SLA Status: {sla_status}

Root Cause Analysis (Confidence: {confidence}%):
{top_rc}

Alarm: {alarm_name}
Reason: {reason}

Dashboard: {dashboard_link}

==================================================
Auto-generated by OutageShield AI Agent
"""

    incident_data = {
        "short_description": short_description[:160],
        "description": work_notes,
        "impact": str(snow_impact),
        "urgency": str(snow_urgency),
        "category": "Software",
        "subcategory": "Application",
        "contact_type": "Monitoring",
        "state": "1",  # New
        "work_notes": f"OutageShield Dashboard: {dashboard_link}"
    }

    if assignment_group:
        incident_data["assignment_group"] = assignment_group
    if caller_id:
        incident_data["caller_id"] = caller_id

    try:
        url = f"{instance_url}/api/now/table/incident"
        data = json.dumps(incident_data).encode('utf-8')
        auth_bytes = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        req.add_header('Authorization', f'Basic {auth_bytes}')
        
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        
        incident_result = result.get('result', {})
        ticket_id = incident_result.get('number', 'UNKNOWN')
        sys_id = incident_result.get('sys_id', '')
        ticket_url = f"{instance_url}/nav_to.do?uri=incident.do?sys_id={sys_id}"
        
        print(f"ServiceNow incident created: {ticket_id}")
        return {
            'system': 'ServiceNow',
            'success': True,
            'ticket_id': ticket_id,
            'ticket_url': ticket_url,
            'sys_id': sys_id
        }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        print(f"ServiceNow HTTP error: {e.code} - {error_body[:200]}")
        return {'system': 'ServiceNow', 'success': False, 'error': f"HTTP {e.code}: {error_body[:100]}"}
    except Exception as e:
        print(f"ServiceNow error: {e}")
        return {'system': 'ServiceNow', 'success': False, 'error': str(e)[:100]}


def store_ticket_info(incident_id, results):
    """Store ticket information in DynamoDB."""
    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        
        # Build ticket info
        tickets_json = json.dumps(results.get('tickets', []))
        primary_ticket_id = results.get('ticket_id', 'N/A')
        primary_ticket_url = results.get('ticket_url', '')
        
        # Determine primary system
        ticket_systems = [t['system'] for t in results.get('tickets', []) if t.get('success')]
        ticket_system = ', '.join(ticket_systems) if ticket_systems else 'None'
        
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET ticket_id = :tid, ticket_system = :ts, ticket_status = :tst, ticket_url = :tu, tickets_all = :ta, workflow_step = :ws',
            ExpressionAttributeValues={
                ':tid': primary_ticket_id,
                ':ts': ticket_system,
                ':tst': 'Open',
                ':tu': primary_ticket_url,
                ':ta': tickets_json,
                ':ws': 'ticket_created'
            }
        )
        print(f"Stored ticket info for {incident_id}: {ticket_system}")
    except Exception as e:
        print(f"DynamoDB store failed: {e}")
'''

# Create zip file
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', LAMBDA_CODE.strip())
zip_buffer.seek(0)

print("=" * 60)
print("Adding ServiceNow Integration to Ticket Integrator Lambda")
print("=" * 60)
print()
print("Features:")
print("  ✓ Jira integration (existing)")
print("  ✓ ServiceNow integration (NEW)")
print("  ✓ Configurable: Jira only, ServiceNow only, or both")
print("  ✓ Automatic severity mapping to ServiceNow impact/urgency")
print("  ✓ Dashboard link in work notes")
print()

# Update Lambda code
response = lambda_client.update_function_code(
    FunctionName='outageshield-ticket-integrator-dev',
    ZipFile=zip_buffer.read()
)
print(f"✓ Lambda code updated! Last modified: {response['LastModified']}")

# Add environment variable for ServiceNow
print()
print("Adding ServiceNow environment variables...")

try:
    config = lambda_client.get_function_configuration(FunctionName='outageshield-ticket-integrator-dev')
    env_vars = config.get('Environment', {}).get('Variables', {})
    env_vars['SERVICENOW_SECRET'] = 'outageshield/servicenow-credentials'
    env_vars['TICKET_SYSTEM'] = 'jira'  # Default to Jira, change to 'servicenow' or 'both'
    
    lambda_client.update_function_configuration(
        FunctionName='outageshield-ticket-integrator-dev',
        Environment={'Variables': env_vars}
    )
    print("✓ Environment variables updated")
except Exception as e:
    print(f"⚠ Environment update: {e}")

print()
print("=" * 60)
print("ServiceNow Setup Instructions")
print("=" * 60)
print()
print("1. Create a secret in AWS Secrets Manager:")
print("   Secret name: outageshield/servicenow-credentials")
print("   Secret value (JSON):")
print('   {')
print('     "instance_url": "https://your-instance.service-now.com",')
print('     "username": "api_user",')
print('     "password": "api_password",')
print('     "assignment_group": "sys_id_of_group",  // optional')
print('     "caller_id": "sys_id_of_caller"         // optional')
print('   }')
print()
print("2. Update TICKET_SYSTEM environment variable:")
print("   - 'jira' = Jira only (default)")
print("   - 'servicenow' = ServiceNow only")
print("   - 'both' = Create tickets in both systems")
print()
print("3. Grant Lambda permission to read the secret:")
print("   Add secretsmanager:GetSecretValue for outageshield/servicenow-credentials")
