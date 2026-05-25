"""
Re-run COMPLETE workflow for ALL incidents:
1. Agent Investigation (6 tools)
2. Remediation Recommendations (6 sources)
3. Ticket Creation (Jira + ServiceNow)
4. SNS Notifications

This updates all incidents with the latest investigation, recommendations, and tickets.
"""
import boto3
import json
import time
import sys

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-incidents-dev')

# Get all incidents
print("=" * 70)
print("OutageShield AI - Complete Refresh")
print("=" * 70)
print("\nFetching all incidents...")
response = table.scan(ProjectionExpression='incident_id, service, title, root_cause, root_causes_raw, created_at, severity_score, business_impact_score, revenue_at_risk, affected_users, sla_status')
incidents = response.get('Items', [])

# Handle pagination
while 'LastEvaluatedKey' in response:
    response = table.scan(
        ProjectionExpression='incident_id, service, title, root_cause, root_causes_raw, created_at, severity_score, business_impact_score, revenue_at_risk, affected_users, sla_status',
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    incidents.extend(response.get('Items', []))

print(f"Found {len(incidents)} incidents to process")
print("=" * 70)

# Stats
stats = {
    'success': 0,
    'error': 0,
    'investigation_sources': {
        'Incident History': 0,
        'OpenSearch Logs': 0,
        'Runbook': 0,
        'Deployment History': 0,
        'X-Ray Traces': 0,
        'AWS Config': 0
    },
    'tickets': {
        'Jira': 0,
        'ServiceNow': 0,
        'Both': 0,
        'Failed': 0
    },
    'recommendations': []
}

for i, item in enumerate(incidents, 1):
    inc_id = item.get('incident_id', '')
    service = item.get('service', 'unknown')
    title = item.get('title', '')
    severity = int(item.get('severity_score', 3))
    biz_impact = int(item.get('business_impact_score', 5))
    revenue = item.get('revenue_at_risk', 'Unknown')
    affected_users = int(item.get('affected_users', 0))
    sla_status = item.get('sla_status', 'Unknown')
    
    print(f"\n[{i}/{len(incidents)}] {inc_id} - {service}")
    
    # Build the event
    event = {
        'signal': {
            'signal_id': inc_id,
            'service': service,
            'alarm_name': title,
            'timestamp': item.get('created_at', '')
        },
        'step2': {
            'severity_score': severity,
            'business_impact_score': biz_impact,
            'revenue_at_risk': revenue,
            'affected_users': affected_users,
            'sla_status': sla_status
        },
        'step3': {
            'root_causes': [],
            'incident_context_id': inc_id
        }
    }
    
    # Parse root causes
    root_causes_raw = item.get('root_causes_raw', '')
    if root_causes_raw:
        try:
            event['step3']['root_causes'] = json.loads(root_causes_raw) if isinstance(root_causes_raw, str) else root_causes_raw
        except:
            pass
    
    root_cause = item.get('root_cause', '')
    if root_cause and not event['step3']['root_causes']:
        event['step3']['root_causes'] = [{'description': root_cause, 'confidence': 75}]
    
    try:
        # ─────────────────────────────────────────────────────────────────
        # Step 1: Agent Investigation (6 tools)
        # ─────────────────────────────────────────────────────────────────
        response = lambda_client.invoke(
            FunctionName='outageshield-agent-invoker-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        result = json.loads(response['Payload'].read().decode('utf-8'))
        investigation = result.get('investigation', '')
        
        # Track sources found
        if '[Source: Incident History' in investigation:
            stats['investigation_sources']['Incident History'] += 1
        if '[Source: OpenSearch' in investigation:
            stats['investigation_sources']['OpenSearch Logs'] += 1
        if '[Source: Runbook' in investigation:
            stats['investigation_sources']['Runbook'] += 1
        if '[Source: Deployment' in investigation:
            stats['investigation_sources']['Deployment History'] += 1
        if '[Source: X-Ray' in investigation:
            stats['investigation_sources']['X-Ray Traces'] += 1
        if '[Source: AWS Config' in investigation:
            stats['investigation_sources']['AWS Config'] += 1
        
        print(f"   ✓ Investigation: {len(investigation)} chars")
        
        # ─────────────────────────────────────────────────────────────────
        # Step 2: Remediation Recommendations (6 sources)
        # ─────────────────────────────────────────────────────────────────
        remediation_event = {
            'incident_id': inc_id,
            'service': service,
            'alarm_name': title,
            'agent_investigation': investigation,
            'root_causes': event['step3']['root_causes']
        }
        
        response = lambda_client.invoke(
            FunctionName='outageshield-remediation-recommend-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(remediation_event)
        )
        rem_result = json.loads(response['Payload'].read().decode('utf-8'))
        rec_count = len(rem_result.get('recommendations', []))
        stats['recommendations'].append(rec_count)
        
        print(f"   ✓ Remediation: {rec_count} recommendations")
        
        # ─────────────────────────────────────────────────────────────────
        # Step 3: Ticket Creation (Jira + ServiceNow)
        # ─────────────────────────────────────────────────────────────────
        ticket_event = {
            'signal': event['signal'],
            'step2': event['step2'],
            'step3': event['step3']
        }
        
        response = lambda_client.invoke(
            FunctionName='outageshield-ticket-integrator-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(ticket_event)
        )
        ticket_result = json.loads(response['Payload'].read().decode('utf-8'))
        tickets = ticket_result.get('tickets', [])
        
        jira_ok = any(t.get('system') == 'Jira' and t.get('success') for t in tickets)
        snow_ok = any(t.get('system') == 'ServiceNow' and t.get('success') for t in tickets)
        
        if jira_ok and snow_ok:
            stats['tickets']['Both'] += 1
            print(f"   ✓ Tickets: Jira + ServiceNow")
        elif jira_ok:
            stats['tickets']['Jira'] += 1
            print(f"   ✓ Tickets: Jira only")
        elif snow_ok:
            stats['tickets']['ServiceNow'] += 1
            print(f"   ✓ Tickets: ServiceNow only")
        else:
            stats['tickets']['Failed'] += 1
            errors = [t.get('error', '')[:30] for t in tickets if not t.get('success')]
            print(f"   ⚠ Tickets: Failed - {errors}")
        
        # ─────────────────────────────────────────────────────────────────
        # Step 4: SNS Notification
        # ─────────────────────────────────────────────────────────────────
        notification_event = {
            'signal': event['signal'],
            'step2': event['step2'],
            'step3': event['step3'],
            'step7': {
                'ticket_id': ticket_result.get('ticket_id', 'N/A'),
                'ticket_url': ticket_result.get('ticket_url', ''),
                'root_cause': event['step3']['root_causes'][0].get('description', '') if event['step3']['root_causes'] else ''
            }
        }
        
        response = lambda_client.invoke(
            FunctionName='outageshield-notification-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(notification_event)
        )
        notif_result = json.loads(response['Payload'].read().decode('utf-8'))
        notif_type = notif_result.get('notification', {}).get('type', 'alert')
        print(f"   ✓ Notification: {notif_type}")
        
        stats['success'] += 1
        
    except Exception as e:
        print(f"   ✗ ERROR: {str(e)[:60]}")
        stats['error'] += 1
    
    # Progress update every 10 incidents
    if i % 10 == 0:
        print(f"\n   --- Processed {i}/{len(incidents)} incidents ---")
        time.sleep(0.5)

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("COMPLETE REFRESH FINISHED!")
print("=" * 70)

print(f"\n📊 Overall Results:")
print(f"   Success: {stats['success']}/{len(incidents)}")
print(f"   Errors:  {stats['error']}/{len(incidents)}")

print(f"\n🔍 Investigation Sources (6 tools):")
for source, count in stats['investigation_sources'].items():
    pct = (count / len(incidents)) * 100 if incidents else 0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(f"   {source:20} {bar} {count:3}/{len(incidents)} ({pct:.0f}%)")

print(f"\n💡 Remediation Recommendations (6 sources):")
avg_recs = sum(stats['recommendations']) / len(stats['recommendations']) if stats['recommendations'] else 0
print(f"   Average per incident: {avg_recs:.1f}")
print(f"   Total recommendations: {sum(stats['recommendations'])}")

print(f"\n🎫 Ticket Creation:")
print(f"   Jira + ServiceNow: {stats['tickets']['Both']}")
print(f"   Jira only:         {stats['tickets']['Jira']}")
print(f"   ServiceNow only:   {stats['tickets']['ServiceNow']}")
print(f"   Failed:            {stats['tickets']['Failed']}")

print("\n" + "=" * 70)
print("Dashboard: https://d2k1km1tzlio49.cloudfront.net")
print("=" * 70)
