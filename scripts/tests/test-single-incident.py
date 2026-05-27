"""
Test a single incident through the full workflow with FULL OUTPUT.
Shows complete tool outputs and step details.
Usage: python scripts/tests/test-single-incident.py [incident_id]
"""
import boto3
import json
import sys
from datetime import datetime, timezone

lambda_client = boto3.client('lambda', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Get incident ID from command line or pick first one
incident_id = sys.argv[1] if len(sys.argv) > 1 else None

if not incident_id:
    # Get first incident from DynamoDB
    table = dynamodb.Table('outageshield-incidents-dev')
    scan = table.scan(Limit=1)
    items = scan.get('Items', [])
    if items:
        incident_id = items[0].get('incident_id')
        print(f"Using incident: {incident_id}")
    else:
        print("No incidents found in DynamoDB")
        exit(1)

# Get incident details
table = dynamodb.Table('outageshield-incidents-dev')
response = table.get_item(Key={'incident_id': incident_id})
incident = response.get('Item', {})

if not incident:
    print(f"Incident {incident_id} not found")
    exit(1)

service = incident.get('service', 'unknown')
alarm_name = incident.get('alarm_name', '')

print('=' * 80)
print(f'TESTING SINGLE INCIDENT: {incident_id}')
print('=' * 80)
print(f'Service: {service}')
print(f'Alarm: {alarm_name}')
print(f'Status: {incident.get("status", "Unknown")}')
print(f'Created: {incident.get("created_at", "Unknown")}')
print('=' * 80)

# Create signal from incident
signal = {
    'signal_id': incident_id,
    'service': service,
    'alarm_name': alarm_name,
    'severity_score': int(incident.get('severity_score', 3)),
    'timestamp': incident.get('created_at', datetime.now(timezone.utc).isoformat())
}

results = {}

# Step 1: Correlation (skip - already done)
print('\n' + '=' * 80)
print('[1/7] CORRELATION - Already exists')
print('=' * 80)
results['correlation'] = {'statusCode': 200, 'incident_context': {'incident_id': incident_id, 'service': service}}
print(f'Incident ID: {incident_id}')
print(f'Service: {service}')

# Step 2: Scoring
print('\n' + '=' * 80)
print('[2/7] SCORING LAMBDA')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-scoring-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({'signal': signal, 'step1': results['correlation']})
    )
    results['scoring'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["scoring"].get("statusCode", "N/A")}')
    print(f'Severity Score: {results["scoring"].get("severity_score", "N/A")}/5')
    print(f'Business Impact: {results["scoring"].get("business_impact_score", "N/A")}/10')
    print(f'Affected Users: {results["scoring"].get("affected_users", "N/A")}')
    print(f'Revenue at Risk: {results["scoring"].get("revenue_at_risk", "N/A")}')
    print(f'\nReasoning: {results["scoring"].get("scoring_reasoning", "N/A")}')
except Exception as e:
    print(f'ERROR: {e}')
    results['scoring'] = {}

# Step 3: RCA
print('\n' + '=' * 80)
print('[3/7] ROOT CAUSE ANALYSIS LAMBDA')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-rootcause-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({'signal': signal, 'step1': results['correlation'], 'step2': results['scoring']})
    )
    results['rca'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["rca"].get("statusCode", "N/A")}')
    root_causes = results['rca'].get('root_causes', [])
    print(f'Root Causes Found: {len(root_causes)}')
    
    for i, rc in enumerate(root_causes, 1):
        print(f'\n  [{i}] {rc.get("description", "N/A")}')
        print(f'      Confidence: {rc.get("confidence", "N/A")}%')
        print(f'      Category: {rc.get("category", "N/A")}')
except Exception as e:
    print(f'ERROR: {e}')
    results['rca'] = {}

# Step 4: Agent Investigation
print('\n' + '=' * 80)
print('[4/7] AGENT INVESTIGATION (6 TOOLS)')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-agent-invoker-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({'signal': signal, 'step3': results['rca']})
    )
    results['agent'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["agent"].get("statusCode", "N/A")}')
    print(f'Tools Called: {results["agent"].get("tools_called", "N/A")}/6')
    print(f'Missing Tools: {results["agent"].get("missing_tools", [])}')
    
    investigation = results['agent'].get('investigation', '')
    print(f'\n--- FULL INVESTIGATION OUTPUT ({len(investigation)} chars) ---\n')
    print(investigation)
    print('\n--- END INVESTIGATION ---')
except Exception as e:
    print(f'ERROR: {e}')
    results['agent'] = {}

# Step 5: Remediation
print('\n' + '=' * 80)
print('[5/7] REMEDIATION LAMBDA')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-remediation-recommend-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'incident_id': incident_id,
            'service': service,
            'alarm_name': alarm_name,
            'agent_investigation': results['agent'].get('investigation', ''),
            'root_causes': results['rca'].get('root_causes', [])
        })
    )
    results['remediation'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["remediation"].get("statusCode", "N/A")}')
    recommendations = results['remediation'].get('recommendations', [])
    print(f'Total Recommendations: {len(recommendations)}')
    
    print('\n--- ALL RECOMMENDATIONS ---')
    for i, rec in enumerate(recommendations, 1):
        print(f'\n[{i}] {rec.get("category", "N/A").upper()}')
        print(f'    Description: {rec.get("description", "N/A")}')
        print(f'    Confidence: {rec.get("confidence", "N/A")}%')
        print(f'    Source: {rec.get("source", "N/A")}')
        print(f'    Reasoning: {rec.get("reasoning", "N/A")}')
except Exception as e:
    print(f'ERROR: {e}')
    results['remediation'] = {}

# Step 6: Summary
print('\n' + '=' * 80)
print('[6/7] SUMMARY LAMBDA')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-remediation-summary-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'signal': signal,
            'step1': results['correlation'],
            'step2': results['scoring'],
            'step3': results['rca'],
            'step3b': {'investigation': results['agent'].get('investigation', '')},
            'step4': {'recommendations': results['remediation'].get('recommendations', [])}
        })
    )
    results['summary'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["summary"].get("statusCode", "N/A")}')
    summary = results['summary'].get('summary', {})
    
    print(f'\n--- AI SUMMARY ---')
    print(summary.get('ai_summary', 'N/A'))
    
    print(f'\n--- RECOMMENDED ACTION ---')
    action = summary.get('recommended_action', {})
    print(f'Type: {action.get("type", "N/A")}')
    print(f'Confidence: {action.get("confidence", "N/A")}%')
    print(f'Description: {action.get("description", "N/A")}')
    
    print(f'\n--- QUICK ACTIONS ({len(summary.get("quick_actions", []))}) ---')
    for i, qa in enumerate(summary.get('quick_actions', []), 1):
        print(f'[{i}] {qa.get("label", "N/A")}')
        print(f'    Command: {qa.get("command", "N/A")}')
    
    print(f'\n--- INVESTIGATION SUMMARY ---')
    inv_summary = summary.get('investigation_summary', {})
    if isinstance(inv_summary, dict):
        print(f'Sources Checked: {inv_summary.get("sources_checked", "N/A")}')
        print(f'Metrics: {inv_summary.get("metrics", {})}')
    else:
        print(f'Data: {inv_summary}')
except Exception as e:
    print(f'ERROR: {e}')
    results['summary'] = {}

# Step 7: Postmortem
print('\n' + '=' * 80)
print('[7/7] POSTMORTEM LAMBDA')
print('=' * 80)
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-postmortem-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps({
            'signal': signal,
            'incident_id': incident_id,
            'service': service,
            'step2': results['scoring'],
            'step3': results['rca'],
            'step3b': {'investigation': results['agent'].get('investigation', '')},
            'step4': {'recommendations': results['remediation'].get('recommendations', [])}
        })
    )
    results['postmortem'] = json.loads(response['Payload'].read())
    
    print(f'Status: {results["postmortem"].get("statusCode", "N/A")}')
    pm = results['postmortem'].get('postmortem', {})
    
    print(f'\n--- POSTMORTEM REPORT ---')
    print(f'\nSummary: {pm.get("summary", "N/A")}')
    print(f'\nRoot Cause: {pm.get("root_cause", "N/A")}')
    print(f'\nDuration: {pm.get("duration", "N/A")}')
    print(f'\nImpact: {pm.get("impact", "N/A")}')
    
    print(f'\n--- PREVENTION STEPS ---')
    for i, step in enumerate(pm.get('prevention', []), 1):
        print(f'[{i}] {step}')
    
    print(f'\n--- INVESTIGATION DATA USED ---')
    inv = pm.get('investigation', {})
    print(f'Sources: {inv.get("sources_checked", [])}')
    print(f'Metrics: {inv.get("metrics", {})}')
    
    print(f'\n--- REMEDIATION DATA USED ---')
    rem = pm.get('remediation', {})
    print(f'Total Recommendations: {rem.get("total_recommendations", 0)}')
    print(f'Categories: {rem.get("categories", [])}')
except Exception as e:
    print(f'ERROR: {e}')
    results['postmortem'] = {}

# Final Summary
print('\n' + '=' * 80)
print('TEST SUMMARY')
print('=' * 80)

steps = [
    ('Correlation', 'correlation', True),
    ('Scoring', 'scoring', results.get('scoring', {}).get('severity_score', 0) > 0),
    ('RCA', 'rca', len(results.get('rca', {}).get('root_causes', [])) > 0),
    ('Agent Investigation', 'agent', results.get('agent', {}).get('tools_called', 0) == 6),
    ('Remediation', 'remediation', len(results.get('remediation', {}).get('recommendations', [])) > 0),
    ('Summary', 'summary', results.get('summary', {}).get('statusCode') == 200),
    ('Postmortem', 'postmortem', results.get('postmortem', {}).get('statusCode') == 200),
]

all_passed = True
for name, key, passed in steps:
    status = '✅ PASS' if passed else '❌ FAIL'
    all_passed = all_passed and passed
    print(f'  {name}: {status}')

print()
print(f'{"✅ ALL STEPS PASSED!" if all_passed else "❌ SOME STEPS FAILED"}')
print('=' * 80)
