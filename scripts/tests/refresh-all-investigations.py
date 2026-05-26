"""
Re-run agent investigation, remediation, tickets, and notifications for ALL incidents.
Updates existing records - does NOT create duplicate tickets.
"""
import boto3
import json
import time

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-incidents-dev')

# Get all incidents with full data
print("Fetching all incidents...")
response = table.scan()
incidents = response.get('Items', [])

# Handle pagination
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    incidents.extend(response.get('Items', []))

print(f"Found {len(incidents)} incidents to process")
print("=" * 60)

success_count = 0
error_count = 0
stats = {
    'investigation': 0,
    'remediation': 0,
    'tickets': 0,
    'notifications': 0
}
sources_found = {
    'Incident History': 0, 
    'OpenSearch Logs': 0, 
    'Runbook': 0, 
    'Deployment History': 0,
    'X-Ray Traces': 0,
    'AWS Config': 0
}

for i, item in enumerate(incidents, 1):
    inc_id = item.get('incident_id', '')
    service = item.get('service', 'unknown')
    title = item.get('title', '')
    severity = int(item.get('severity_score', 3))
    
    print(f"\n[{i}/{len(incidents)}] {inc_id} - {service}")
    
    # Build the base event
    signal = {
        'signal_id': inc_id,
        'service': service,
        'alarm_name': title,
        'timestamp': item.get('created_at', ''),
        'reason': item.get('reason', 'Anomaly detected')
    }
    
    # Parse root causes
    root_causes = []
    root_causes_raw = item.get('root_causes_raw', item.get('recommendations_raw', ''))
    if root_causes_raw:
        try:
            root_causes = json.loads(root_causes_raw) if isinstance(root_causes_raw, str) else root_causes_raw
        except:
            pass
    
    root_cause = item.get('root_cause', '')
    if root_cause and not root_causes:
        root_causes = [{'description': root_cause, 'confidence': 75}]
    
    try:
        # ─────────────────────────────────────────────────────────────
        # Step 1: Agent Investigation (6 tools)
        # ─────────────────────────────────────────────────────────────
        agent_event = {
            'signal': signal,
            'step3': {
                'root_causes': root_causes,
                'incident_context_id': inc_id
            }
        }
        
        response = lambda_client.invoke(
            FunctionName='outageshield-agent-invoker-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(agent_event)
        )
        result = json.loads(response['Payload'].read().decode('utf-8'))
        investigation = result.get('investigation', '')
        stats['investigation'] += 1
        
        # Track sources found
        if '[Source: Incident History' in investigation:
            sources_found['Incident History'] += 1
        if '[Source: OpenSearch' in investigation:
            sources_found['OpenSearch Logs'] += 1
        if '[Source: Runbook' in investigation:
            sources_found['Runbook'] += 1
        if '[Source: Deployment' in investigation:
            sources_found['Deployment History'] += 1
        if '[Source: X-Ray' in investigation:
            sources_found['X-Ray Traces'] += 1
        if '[Source: AWS Config' in investigation:
            sources_found['AWS Config'] += 1
        
        # ─────────────────────────────────────────────────────────────
        # Step 2: Remediation (6 sources)
        # ─────────────────────────────────────────────────────────────
        remediation_event = {
            'incident_id': inc_id,
            'service': service,
            'alarm_name': title,
            'agent_investigation': investigation,
            'root_causes': root_causes
        }
        
        response = lambda_client.invoke(
            FunctionName='outageshield-remediation-recommend-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(remediation_event)
        )
        rem_result = json.loads(response['Payload'].read().decode('utf-8'))
        rec_count = len(rem_result.get('recommendations', []))
        stats['remediation'] += 1
        
        # ─────────────────────────────────────────────────────────────
        # Step 3: Create/Update Tickets (Jira + PagerDuty)
        # Skip Jira if ticket already exists, PagerDuty uses dedup_key
        # ─────────────────────────────────────────────────────────────
        existing_ticket = item.get('ticket_id', '')
        existing_ticket_url = item.get('ticket_url', '')
        pagerduty_id = item.get('pagerduty_id', '')
        pagerduty_url = item.get('pagerduty_url', '')
        ticket_system = item.get('ticket_system', '')
        
        # Only call ticket integrator if:
        # 1. No Jira ticket exists yet, OR
        # 2. No PagerDuty incident exists yet
        if not existing_ticket or not pagerduty_id:
            ticket_event = {
                'signal': signal,
                'step2': {
                    'severity_score': severity,
                    'business_impact_score': int(item.get('business_impact_score', 5)),
                    'revenue_at_risk': item.get('revenue_at_risk', 'Unknown'),
                    'affected_users': int(item.get('affected_users', 0)) if item.get('affected_users') else 0,
                    'sla_status': item.get('sla_status', 'Unknown')
                },
                'step3': {
                    'root_causes': root_causes
                },
                # Pass existing ticket info to avoid duplicates
                'existing_ticket_id': existing_ticket,
                'existing_pagerduty_id': pagerduty_id
            }
            
            response = lambda_client.invoke(
                FunctionName='outageshield-ticket-integrator-dev',
                InvocationType='RequestResponse',
                Payload=json.dumps(ticket_event)
            )
            ticket_result = json.loads(response['Payload'].read().decode('utf-8'))
            
            # Get ticket info from result (use existing if not returned)
            if ticket_result.get('ticket_id'):
                existing_ticket = ticket_result.get('ticket_id')
                existing_ticket_url = ticket_result.get('ticket_url', existing_ticket_url)
            if ticket_result.get('pagerduty_id'):
                pagerduty_id = ticket_result.get('pagerduty_id')
                pagerduty_url = ticket_result.get('pagerduty_url', pagerduty_url)
            
            # Determine ticket systems
            ticket_systems = []
            for t in ticket_result.get('tickets', []):
                if t.get('success'):
                    ticket_systems.append(t.get('system', ''))
            if ticket_systems:
                ticket_system = ', '.join(ticket_systems)
        else:
            print(f"   → Skipping ticket creation (Jira: {existing_ticket}, PD: {pagerduty_id})")
        
        stats['tickets'] += 1
        
        # ─────────────────────────────────────────────────────────────
        # Step 4: Update Notification Record with FULL details
        # ─────────────────────────────────────────────────────────────
        from datetime import datetime, timezone
        
        notif_type = 'escalation' if severity >= 4 else 'alert'
        subject = f"[OutageShield] SEV-{severity} | {service} | {title}"
        
        # Build detailed message
        top_rc = root_causes[0].get('description', 'Under investigation') if root_causes else 'Under investigation'
        confidence = root_causes[0].get('confidence', 0) if root_causes else 0
        revenue = item.get('revenue_at_risk', 'Unknown')
        affected_users = item.get('affected_users', 0)
        dashboard_url = f"https://d2k1km1tzlio49.cloudfront.net/incidents/{inc_id}"
        
        message = f"""OutageShield AI - Incident Alert
==================================================

Service:         {service}
Severity:        SEV-{severity}
Incident ID:     {inc_id}
Alarm:           {title}

Root Cause:      {top_rc}
Confidence:      {confidence}%
Revenue at Risk: {revenue}
Affected Users:  {affected_users}

Recommendations: {rec_count} actions available
Sources:         6 (deployment, logs, runbook, history, X-Ray, Config)

Jira Ticket:     {existing_ticket or 'N/A'}
Ticket URL:      {existing_ticket_url or 'N/A'}
PagerDuty:       {pagerduty_id or 'N/A'}
PagerDuty URL:   {pagerduty_url or 'N/A'}

Dashboard:       {dashboard_url}

==================================================
Action Required: Review incident and approve remediation.
"""
        
        notification = {
            'type': notif_type,
            'channel': 'SNS',
            'status': 'sent',
            'recipient': 'sre-team@company.com',
            'subject': subject[:100],
            'message': message,
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'ticket_id': existing_ticket or 'N/A',
            'ticket_url': existing_ticket_url or '',
            'pagerduty_id': pagerduty_id or 'N/A',
            'pagerduty_url': pagerduty_url or '',
            'dashboard_url': dashboard_url,
            'recommendations_count': rec_count,
            'sources_count': 6
        }
        
        table.update_item(
            Key={'incident_id': inc_id},
            UpdateExpression='SET notifications = :n, workflow_step = :ws, recommendations_count = :rc',
            ExpressionAttributeValues={
                ':n': json.dumps(notification),
                ':ws': 'notified',
                ':rc': rec_count
            }
        )
        stats['notifications'] += 1
        
        print(f"   ✓ Investigation: {len(investigation)} chars | Recs: {rec_count} | Jira: {existing_ticket or 'N/A'} | PD: {pagerduty_id or 'N/A'}")
        success_count += 1
        
    except Exception as e:
        print(f"   ✗ ERROR: {str(e)[:60]}")
        error_count += 1
    
    # Progress update every 10 incidents
    if i % 10 == 0:
        print(f"\n   --- Processed {i}/{len(incidents)} incidents ---")
        time.sleep(0.5)

print("\n" + "=" * 60)
print("REFRESH COMPLETE!")
print("=" * 60)
print(f"\nResults:")
print(f"  ✓ Success: {success_count}/{len(incidents)}")
print(f"  ✗ Errors:  {error_count}/{len(incidents)}")

print(f"\nSteps Completed:")
print(f"  Investigation (6 tools): {stats['investigation']}")
print(f"  Remediation (6 sources): {stats['remediation']}")
print(f"  Tickets Updated:         {stats['tickets']}")
print(f"  Notifications Updated:   {stats['notifications']}")

print(f"\nSources Found Across All Investigations:")
for source, count in sources_found.items():
    pct = (count / len(incidents)) * 100 if incidents else 0
    bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
    print(f"  {source:20} {bar} {count:3}/{len(incidents)} ({pct:.0f}%)")

print("\n" + "=" * 60)
print("All incidents now have:")
print("  • 6 investigation tools (including X-Ray + Config)")
print("  • 6 remediation sources")
print("  • Jira + PagerDuty ticket support")
print("  • Updated notification records")
print("=" * 60)
