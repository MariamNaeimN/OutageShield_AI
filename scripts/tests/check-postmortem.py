"""Check if postmortem is useful - based on actual investigation and remediation data."""
import boto3
import json
import sys

ddb = boto3.resource('dynamodb', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

inc_id = sys.argv[1] if len(sys.argv) > 1 else 'INC-C7E7E6CF'

print('=' * 80)
print(f'POSTMORTEM ANALYSIS FOR: {inc_id}')
print('=' * 80)

# Check postmortems table
postmortems_table = ddb.Table('outageshield-postmortems-dev')
from boto3.dynamodb.conditions import Attr

try:
    response = postmortems_table.scan(
        FilterExpression=Attr('incident_id').eq(inc_id)
    )
    postmortems = response.get('Items', [])
except Exception as e:
    print(f"Error scanning postmortems table: {e}")
    postmortems = []

# Get incident data for comparison
incidents_table = ddb.Table('outageshield-incidents-dev')
incident_resp = incidents_table.get_item(Key={'incident_id': inc_id})
incident = incident_resp.get('Item', {})

print('\n' + '=' * 80)
print('1. ACTUAL DATA FROM INVESTIGATION & REMEDIATION')
print('=' * 80)

root_cause = incident.get('root_cause', 'N/A')
investigation = incident.get('agent_investigation', '')
recommendations_raw = incident.get('recommendations_raw', '[]')
recommendations = json.loads(recommendations_raw) if isinstance(recommendations_raw, str) else recommendations_raw

print(f"\n📋 ROOT CAUSE (from RCA):")
print(f"   {root_cause}")

print(f"\n📊 KEY INVESTIGATION FINDINGS:")
# Extract key metrics
import re
if investigation:
    errors_match = re.search(r'Errors:\s*(\d+)', investigation)
    faults_match = re.search(r'Faults:\s*(\d+)', investigation)
    queue_match = re.search(r'queue\s*depth[:\s]*\(?(\d+)\)?', investigation.lower())
    
    if errors_match:
        print(f"   - X-Ray Errors: {errors_match.group(1)}")
    if faults_match:
        print(f"   - X-Ray Faults: {faults_match.group(1)}")
    if queue_match:
        print(f"   - Queue Depth: {queue_match.group(1)}")
    
    # Check what sources were used
    sources = []
    if '[Source: Incident History' in investigation:
        sources.append('Incident History')
    if '[Source: OpenSearch' in investigation:
        sources.append('OpenSearch Logs')
    if '[Source: Runbook' in investigation:
        sources.append('Runbook')
    if '[Source: Deployment' in investigation:
        sources.append('Deployment History')
    if '[Source: X-Ray' in investigation:
        sources.append('X-Ray Traces')
    if '[Source: AWS Config' in investigation:
        sources.append('AWS Config')
    print(f"   - Data Sources: {', '.join(sources)}")

print(f"\n🔧 REMEDIATION RECOMMENDATIONS ({len(recommendations)} total):")
for i, rec in enumerate(recommendations[:3], 1):
    print(f"   {i}. [{rec.get('category', 'N/A')}] {rec.get('description', 'N/A')[:60]}...")

if postmortems:
    print('\n' + '=' * 80)
    print('2. EXISTING POSTMORTEM')
    print('=' * 80)
    
    pm = postmortems[0]  # Get the latest
    print(f"\n📝 Postmortem ID: {pm.get('postmortem_id')}")
    print(f"📅 Created: {pm.get('created_at')}")
    print(f"📊 Status: {pm.get('status')}")
    
    print(f"\n📋 SUMMARY:")
    print(f"   {pm.get('summary', 'N/A')}")
    
    print(f"\n🎯 ROOT CAUSE (in postmortem):")
    print(f"   {pm.get('root_cause', 'N/A')}")
    
    print(f"\n⏱️ DURATION:")
    print(f"   {pm.get('duration', 'N/A')}")
    
    print(f"\n👥 IMPACT:")
    print(f"   {pm.get('impact_summary', 'N/A')}")
    
    print(f"\n🛡️ PREVENTION STEPS:")
    prevention = pm.get('prevention', '[]')
    if isinstance(prevention, str):
        prevention = json.loads(prevention)
    for i, step in enumerate(prevention, 1):
        print(f"   {i}. {step}")
    
    # VERIFY: Is postmortem using actual data?
    print('\n' + '=' * 80)
    print('3. VERIFICATION: Is Postmortem Based on Actual Data?')
    print('=' * 80)
    
    pm_root_cause = pm.get('root_cause', '').lower()
    actual_root_cause = root_cause.lower()
    
    # Check root cause match
    if actual_root_cause[:30] in pm_root_cause or pm_root_cause[:30] in actual_root_cause:
        print(f"\n✅ ROOT CAUSE MATCHES: Postmortem uses actual RCA root cause")
    else:
        print(f"\n❌ ROOT CAUSE MISMATCH:")
        print(f"   Actual: {root_cause[:60]}...")
        print(f"   Postmortem: {pm.get('root_cause', 'N/A')[:60]}...")
    
    # Check if prevention steps are specific
    prevention_text = ' '.join(prevention).lower() if prevention else ''
    if 'queue' in prevention_text or 'scaling' in prevention_text or 'capacity' in prevention_text:
        print(f"✅ PREVENTION STEPS: Specific to the root cause (mentions queue/scaling/capacity)")
    else:
        print(f"⚠️ PREVENTION STEPS: May be generic (doesn't mention queue/scaling/capacity)")
    
    # Check if impact uses actual numbers
    impact = pm.get('impact_summary', '').lower()
    if 'user' in impact or 'revenue' in impact:
        print(f"✅ IMPACT: Includes user/revenue impact data")
    else:
        print(f"⚠️ IMPACT: May not include specific numbers")

else:
    print('\n' + '=' * 80)
    print('2. NO POSTMORTEM FOUND - GENERATING ONE')
    print('=' * 80)
    
    # Generate postmortem
    print("\n🚀 Invoking postmortem Lambda...")
    
    # Build event similar to Step Functions
    event = {
        'signal': {
            'signal_id': inc_id,
            'service': incident.get('service', 'unknown'),
            'alarm_name': incident.get('title', ''),
        },
        'incident_id': inc_id,
        'service': incident.get('service', 'unknown'),
        'step2': {
            'severity_score': incident.get('severity', 3),
            'affected_users': incident.get('affected_users', 0),
            'revenue_at_risk': incident.get('revenue_at_risk', 'Unknown'),
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
    
    response = lambda_client.invoke(
        FunctionName='outageshield-postmortem-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(event)
    )
    
    result = json.loads(response['Payload'].read().decode('utf-8'))
    print(f"\n✅ Postmortem Generated!")
    
    pm = result.get('postmortem', {})
    
    print(f"\n📋 SUMMARY:")
    print(f"   {pm.get('summary', 'N/A')}")
    
    print(f"\n🎯 ROOT CAUSE:")
    print(f"   {pm.get('root_cause', 'N/A')}")
    
    print(f"\n⏱️ DURATION:")
    print(f"   {pm.get('duration', 'N/A')}")
    
    print(f"\n👥 IMPACT:")
    print(f"   {pm.get('impact', 'N/A')}")
    
    print(f"\n🛡️ PREVENTION STEPS:")
    prevention = pm.get('prevention', [])
    for i, step in enumerate(prevention, 1):
        print(f"   {i}. {step}")
    
    # Verify
    print('\n' + '=' * 80)
    print('3. VERIFICATION: Is Postmortem Based on Actual Data?')
    print('=' * 80)
    
    pm_root_cause = pm.get('root_cause', '').lower()
    actual_root_cause = root_cause.lower()
    
    if actual_root_cause[:30] in pm_root_cause or pm_root_cause[:30] in actual_root_cause:
        print(f"\n✅ ROOT CAUSE MATCHES: Postmortem uses actual RCA root cause")
    else:
        print(f"\n❌ ROOT CAUSE MISMATCH")
    
    prevention_text = ' '.join(prevention).lower() if prevention else ''
    if 'queue' in prevention_text or 'scaling' in prevention_text or 'capacity' in prevention_text:
        print(f"✅ PREVENTION STEPS: Specific to the root cause")
    else:
        print(f"⚠️ PREVENTION STEPS: May be generic")

print('\n' + '=' * 80)
print('DONE')
print('=' * 80)
