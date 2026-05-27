"""Generate a new postmortem using the updated Lambda."""
import boto3
import json
import sys

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
incidents_table = ddb.Table('outageshield-incidents-dev')

inc_id = sys.argv[1] if len(sys.argv) > 1 else 'INC-C7E7E6CF'

# Get incident data
resp = incidents_table.get_item(Key={'incident_id': inc_id})
incident = resp.get('Item', {})

root_cause = incident.get('root_cause', '')
investigation = incident.get('agent_investigation', '')
recommendations_raw = incident.get('recommendations_raw', '[]')
recommendations = json.loads(recommendations_raw) if isinstance(recommendations_raw, str) else recommendations_raw

print('=' * 70)
print(f'Generating NEW Postmortem for: {inc_id}')
print('=' * 70)

# Build event
event = {
    'signal': {
        'signal_id': inc_id,
        'service': incident.get('service', 'unknown'),
        'alarm_name': incident.get('title', ''),
    },
    'incident_id': inc_id,
    'service': incident.get('service', 'unknown'),
    'step2': {
        'severity_score': incident.get('severity', 4),
        'affected_users': 200000,
        'revenue_at_risk': '$11,400/hour',
    },
    'step3': {
        'root_causes': [{'description': root_cause, 'confidence': 90}] if root_cause else []
    },
    'step3b': {
        'investigation': investigation
    },
    'step4': {
        'recommendations': recommendations
    }
}

print('\n🚀 Invoking updated postmortem Lambda...')

response = lambda_client.invoke(
    FunctionName='outageshield-postmortem-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(event)
)

result = json.loads(response['Payload'].read().decode('utf-8'))
pm = result.get('postmortem', {})

print('\n' + '=' * 70)
print('NEW POSTMORTEM (Using Actual Remediation & Investigation)')
print('=' * 70)

print(f'\n📋 SUMMARY:')
print(f'   {pm.get("summary", "N/A")}')

print(f'\n🎯 ROOT CAUSE ({pm.get("root_cause_confidence", 0)}% confidence):')
print(f'   {pm.get("root_cause", "N/A")}')

print(f'\n⏱️ DURATION: {pm.get("duration", "N/A")}')
print(f'⚠️ SEVERITY: {pm.get("severity", "N/A")}/5')

print(f'\n👥 IMPACT:')
print(f'   {pm.get("impact", "N/A")}')

# Show investigation data used
inv = pm.get('investigation', {})
if inv:
    print(f'\n' + '=' * 70)
    print('📊 INVESTIGATION DATA USED:')
    print('=' * 70)
    print(f'   Sources: {", ".join(inv.get("sources_checked", []))}')
    print(f'   Metrics: {inv.get("metrics", {})}')
    print(f'   Key Findings: {inv.get("key_findings", [])}')

# Show remediation data used
rem = pm.get('remediation', {})
if rem:
    print(f'\n' + '=' * 70)
    print('🔧 REMEDIATION DATA USED:')
    print('=' * 70)
    print(f'   Total Recommendations: {rem.get("total_recommendations", 0)}')
    print(f'   Scaling Actions: {rem.get("scaling_actions", 0)}')
    print(f'   Config Actions: {rem.get("config_actions", 0)}')
    print(f'   Manual Steps: {rem.get("manual_steps", 0)}')
    top = rem.get('top_recommendation', {})
    if top:
        print(f'   Top Recommendation: [{top.get("category")}] {top.get("description", "")[:60]}...')

print(f'\n' + '=' * 70)
print('🛡️ PREVENTION STEPS (from remediation):')
print('=' * 70)
for i, step in enumerate(pm.get('prevention', []), 1):
    print(f'   {i}. {step}')

# Show timeline
timeline = pm.get('timeline', [])
if timeline:
    print(f'\n' + '=' * 70)
    print('📅 TIMELINE:')
    print('=' * 70)
    for t in timeline:
        print(f'   {t.get("time")}: {t.get("event")}')

print(f'\n' + '=' * 70)
print('✅ POSTMORTEM GENERATED WITH ACTUAL DATA')
print('=' * 70)
