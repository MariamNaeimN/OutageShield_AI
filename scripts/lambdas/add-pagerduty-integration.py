"""
Add PagerDuty integration to the ticket-integrator Lambda.
Supports Jira + PagerDuty for comprehensive incident management.
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
import urllib.request
import urllib.error
import base64
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
sm = boto3.client('secretsmanager')

INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
JIRA_SECRET = os.environ.get('JIRA_SECRET', 'outageshield/jira-credentials')
PAGERDUTY_SECRET = os.environ.get('PAGERDUTY_SECRET', 'outageshield/pagerduty-credentials')
TICKET_SYSTEM = os.environ.get('TICKET_SYSTEM', 'jira')  # 'jira', 'pagerduty', 'both'
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://d2k1km1tzlio49.cloudfront.net')


def lambda_handler(event, context):
    """
    Create tickets in Jira and/or PagerDuty based on configuration.
    Skips creation if ticket already exists (prevents duplicates).
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
    
    # Check for existing tickets (passed from caller or from DynamoDB)
    existing_jira = event.get('existing_ticket_id', '')
    existing_pd = event.get('existing_pagerduty_id', '')
    
    # If not passed, check DynamoDB
    if not existing_jira or not existing_pd:
        try:
            table = dynamodb.Table(INCIDENTS_TABLE)
            item = table.get_item(Key={'incident_id': incident_id}).get('Item', {})
            if not existing_jira:
                existing_jira = item.get('ticket_id', '')
            if not existing_pd:
                existing_pd = item.get('pagerduty_id', '')
        except Exception as e:
            print(f"DynamoDB lookup failed: {e}")

    results = {
        'statusCode': 200,
        'tickets': [],
        'severity': severity,
        'root_cause': top_rc
    }

    # Create Jira ticket (only if not exists)
    if TICKET_SYSTEM in ['jira', 'both']:
        if existing_jira and existing_jira != 'N/A':
            print(f"Jira ticket already exists: {existing_jira}, skipping creation")
            results['tickets'].append({
                'system': 'Jira',
                'success': True,
                'ticket_id': existing_jira,
                'ticket_url': f"https://corpinfollc.atlassian.net/browse/{existing_jira}",
                'skipped': True
            })
            results['ticket_id'] = existing_jira
            results['ticket_url'] = f"https://corpinfollc.atlassian.net/browse/{existing_jira}"
        else:
            jira_result = create_jira_ticket(
                incident_id, service, severity, biz_impact, revenue,
                affected_users, sla_status, top_rc, confidence, alarm_name, reason
            )
            results['tickets'].append(jira_result)
            if jira_result.get('success'):
                results['ticket_id'] = jira_result['ticket_id']
                results['ticket_url'] = jira_result['ticket_url']

    # Create PagerDuty incident (uses dedup_key, so safe to call again)
    if TICKET_SYSTEM in ['pagerduty', 'both']:
        pd_result = create_pagerduty_incident(
            incident_id, service, severity, biz_impact, revenue,
            affected_users, sla_status, top_rc, confidence, alarm_name, reason
        )
        results['tickets'].append(pd_result)
        if pd_result.get('success'):
            if 'ticket_id' not in results:
                results['ticket_id'] = pd_result['ticket_id']
                results['ticket_url'] = pd_result['ticket_url']
            results['pagerduty_id'] = pd_result['ticket_id']
            results['pagerduty_url'] = pd_result['ticket_url']

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


def create_pagerduty_incident(incident_id, service, severity, biz_impact, revenue,
                               affected_users, sla_status, top_rc, confidence, alarm_name, reason):
    """Create a PagerDuty incident via Events API v2."""
    try:
        secret = sm.get_secret_value(SecretId=PAGERDUTY_SECRET)
        creds = json.loads(secret['SecretString'])
        routing_key = creds['routing_key']  # Integration key from PagerDuty service
        # Optional: API key for REST API operations
        api_key = creds.get('api_key', '')
    except Exception as e:
        print(f"Failed to get PagerDuty credentials: {e}")
        return {'system': 'PagerDuty', 'success': False, 'error': str(e)[:100]}

    # Map severity to PagerDuty severity
    # PagerDuty: critical, error, warning, info
    severity_map = {5: 'critical', 4: 'critical', 3: 'error', 2: 'warning', 1: 'info'}
    pd_severity = severity_map.get(severity, 'error')

    dashboard_link = f"{DASHBOARD_URL}/incidents/{incident_id}"

    # PagerDuty Events API v2 payload
    event_payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": incident_id,  # Prevents duplicate incidents
        "payload": {
            "summary": f"[OutageShield] SEV-{severity} | {service} | {alarm_name}",
            "source": "OutageShield AI",
            "severity": pd_severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": service,
            "group": "cloud-infrastructure",
            "class": "outage-detection",
            "custom_details": {
                "incident_id": incident_id,
                "service": service,
                "severity_score": severity,
                "business_impact": biz_impact,
                "revenue_at_risk": str(revenue),
                "affected_users": affected_users,
                "sla_status": sla_status,
                "root_cause": top_rc,
                "confidence": f"{confidence}%",
                "alarm_name": alarm_name,
                "reason": reason,
                "dashboard_url": dashboard_link
            }
        },
        "links": [
            {
                "href": dashboard_link,
                "text": "View in OutageShield Dashboard"
            }
        ],
        "images": []
    }

    try:
        url = "https://events.pagerduty.com/v2/enqueue"
        data = json.dumps(event_payload).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        
        dedup_key = result.get('dedup_key', incident_id)
        # PagerDuty doesn't return incident URL directly from Events API
        # We construct a search URL or use the dedup_key
        ticket_url = f"https://app.pagerduty.com/incidents?search={dedup_key}"
        
        print(f"PagerDuty incident created: {dedup_key}")
        return {
            'system': 'PagerDuty',
            'success': True,
            'ticket_id': f"PD-{dedup_key[:8].upper()}",
            'ticket_url': ticket_url,
            'dedup_key': dedup_key,
            'status': result.get('status', 'success'),
            'message': result.get('message', 'Event processed')
        }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        print(f"PagerDuty HTTP error: {e.code} - {error_body[:200]}")
        return {'system': 'PagerDuty', 'success': False, 'error': f"HTTP {e.code}: {error_body[:100]}"}
    except Exception as e:
        print(f"PagerDuty error: {e}")
        return {'system': 'PagerDuty', 'success': False, 'error': str(e)[:100]}


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
        
        update_expr = 'SET ticket_id = :tid, ticket_system = :ts, ticket_status = :tst, ticket_url = :tu, tickets_all = :ta, workflow_step = :ws'
        expr_values = {
            ':tid': primary_ticket_id,
            ':ts': ticket_system,
            ':tst': 'Open',
            ':tu': primary_ticket_url,
            ':ta': tickets_json,
            ':ws': 'ticket_created'
        }
        
        # Add PagerDuty specific fields if present
        if results.get('pagerduty_id'):
            update_expr += ', pagerduty_id = :pdid, pagerduty_url = :pdurl'
            expr_values[':pdid'] = results['pagerduty_id']
            expr_values[':pdurl'] = results['pagerduty_url']
        
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
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
print("Adding PagerDuty Integration to Ticket Integrator Lambda")
print("=" * 60)
print()
print("Features:")
print("  ✓ Jira integration (existing)")
print("  ✓ PagerDuty integration (NEW)")
print("  ✓ Configurable: Jira only, PagerDuty only, or both")
print("  ✓ PagerDuty Events API v2")
print("  ✓ Severity mapping to PagerDuty levels")
print("  ✓ Deduplication key prevents duplicate incidents")
print("  ✓ Dashboard link in custom details")
print()

# Update Lambda code
response = lambda_client.update_function_code(
    FunctionName='outageshield-ticket-integrator-dev',
    ZipFile=zip_buffer.read()
)
print(f"✓ Lambda code updated! Last modified: {response['LastModified']}")

# Create PagerDuty secret if it doesn't exist
print()
print("Creating PagerDuty credentials secret...")

sm = boto3.client('secretsmanager', region_name='us-east-1')
try:
    sm.create_secret(
        Name='outageshield/pagerduty-credentials',
        SecretString=json.dumps({
            "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY",
            "api_key": ""
        })
    )
    print("✓ PagerDuty secret created")
except sm.exceptions.ResourceExistsException:
    print("✓ PagerDuty secret already exists")
except Exception as e:
    print(f"⚠ PagerDuty secret: {e}")

# Add environment variable
print()
print("Adding PagerDuty environment variables...")

import time
time.sleep(3)  # Wait for Lambda update to complete

try:
    config = lambda_client.get_function_configuration(FunctionName='outageshield-ticket-integrator-dev')
    env_vars = config.get('Environment', {}).get('Variables', {})
    env_vars['PAGERDUTY_SECRET'] = 'outageshield/pagerduty-credentials'
    env_vars['TICKET_SYSTEM'] = 'both'  # Enable both Jira and PagerDuty
    
    lambda_client.update_function_configuration(
        FunctionName='outageshield-ticket-integrator-dev',
        Environment={'Variables': env_vars}
    )
    print("✓ Environment variables updated (TICKET_SYSTEM=both)")
except Exception as e:
    print(f"⚠ Environment update: {e}")

print()
print("=" * 60)
print("PagerDuty Setup Instructions")
print("=" * 60)
print()
print("1. Sign up for PagerDuty (free tier available):")
print("   https://www.pagerduty.com/sign-up-free/")
print()
print("2. Create a Service in PagerDuty:")
print("   - Go to Services > Service Directory > + New Service")
print("   - Name: 'OutageShield AI'")
print("   - Integration: Select 'Events API v2'")
print("   - Copy the 'Integration Key' (routing key)")
print()
print("3. Update the secret in AWS:")
print('   aws secretsmanager update-secret \\')
print('     --secret-id outageshield/pagerduty-credentials \\')
print('     --secret-string \'{"routing_key":"YOUR_INTEGRATION_KEY","api_key":""}\'')
print()
print("4. TICKET_SYSTEM options:")
print("   - 'jira' = Jira only")
print("   - 'pagerduty' = PagerDuty only")
print("   - 'both' = Create in both systems (current)")
print()
print("=" * 60)
