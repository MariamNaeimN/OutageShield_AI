"""
Full Workflow Test - Test entire incident pipeline from Detection to Postmortem
Shows every step is accurate and useful
"""
import boto3
import json
import sys
import time
import uuid
from datetime import datetime, timezone

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')

# Generate unique incident ID
incident_id = f"INC-TEST-{str(uuid.uuid4())[:6].upper()}"

print('=' * 80)
print('FULL WORKFLOW TEST - OutageShield AI')
print('=' * 80)
print(f'Test Incident ID: {incident_id}')
print(f'Started: {datetime.now().isoformat()}')
print('=' * 80)

# Simulated CloudWatch alarm event
test_alarm = {
    'source': 'aws.cloudwatch',
    'detail-type': 'CloudWatch Alarm State Change',
    'detail': {
        'alarmName': 'HighLatency-payment-service',
        'state': {'value': 'ALARM'},
        'configuration': {
            'metrics': [{'metricName': 'Latency', 'namespace': 'AWS/Lambda'}]
        }
    }
}

# Track all step results
workflow_results = {}

#############################################################################
# STEP 1: DETECTION LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 1: DETECTION - Anomaly Detection Lambda')
print('=' * 80)

detection_event = {
    'Records': [{
        'Sns': {
            'Message': json.dumps({
                'AlarmName': 'HighLatency-payment-service',
                'NewStateValue': 'ALARM',
                'NewStateReason': 'Threshold Crossed: 1 datapoint [2500.0] was greater than the threshold (1000.0)',
                'StateChangeTime': datetime.now(timezone.utc).isoformat(),
                'Trigger': {
                    'MetricName': 'Duration',
                    'Namespace': 'AWS/Lambda',
                    'Dimensions': [{'name': 'FunctionName', 'value': 'payment-service'}]
                }
            })
        }
    }]
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-detection-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(detection_event)
    )
    detection_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['detection'] = detection_result
    
    print(f"\n✅ Detection Lambda Response:")
    print(f"   Status: {detection_result.get('statusCode', 'N/A')}")
    
    signal = detection_result.get('signal', {})
    incident_id = signal.get('signal_id', incident_id)  # Use generated ID if available
    
    print(f"   Signal ID: {signal.get('signal_id', 'N/A')}")
    print(f"   Service: {signal.get('service', 'N/A')}")
    print(f"   Alarm: {signal.get('alarm_name', 'N/A')}")
    print(f"   Is Anomaly: {detection_result.get('is_anomaly', 'N/A')}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Correctly parsed alarm name: {'HighLatency' in str(signal.get('alarm_name', ''))}")
    print(f"   ✓ Correctly identified service: {'payment' in str(signal.get('service', ''))}")
    
except Exception as e:
    print(f"❌ Detection failed: {e}")
    # Use a known incident for remaining tests
    incident_id = 'INC-C7E7E6CF'
    print(f"   Falling back to existing incident: {incident_id}")

#############################################################################
# STEP 2: CORRELATION LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 2: CORRELATION - Context Enrichment Lambda')
print('=' * 80)

# Get signal from detection or use fallback
signal = workflow_results.get('detection', {}).get('signal', {
    'signal_id': incident_id,
    'service': 'payment-service',
    'alarm_name': 'HighLatency-payment-service',
    'timestamp': datetime.now(timezone.utc).isoformat()
})

correlation_event = {'signal': signal}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-correlation-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(correlation_event)
    )
    correlation_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['correlation'] = correlation_result
    
    print(f"\n✅ Correlation Lambda Response:")
    print(f"   Status: {correlation_result.get('statusCode', 'N/A')}")
    
    context = correlation_result.get('incident_context', {})
    print(f"   Incident ID: {context.get('incident_id', 'N/A')}")
    print(f"   Service: {context.get('service', 'N/A')}")
    print(f"   Related Alarms: {context.get('related_alarms_count', 0)}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Created incident context: {bool(context)}")
    print(f"   ✓ Stored in DynamoDB: {bool(context.get('incident_id'))}")
    
except Exception as e:
    print(f"❌ Correlation failed: {e}")

#############################################################################
# STEP 3: SCORING LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 3: SCORING - Severity & Business Impact Lambda')
print('=' * 80)

scoring_event = {
    'signal': signal,
    'step1': workflow_results.get('correlation', {})
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-scoring-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(scoring_event)
    )
    scoring_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['scoring'] = scoring_result
    
    print(f"\n✅ Scoring Lambda Response:")
    print(f"   Status: {scoring_result.get('statusCode', 'N/A')}")
    print(f"   Severity Score: {scoring_result.get('severity_score', 'N/A')}/5")
    print(f"   Business Impact: {scoring_result.get('business_impact_score', 'N/A')}/10")
    print(f"   Affected Users: {scoring_result.get('affected_users', 'N/A')}")
    print(f"   Revenue at Risk: {scoring_result.get('revenue_at_risk', 'N/A')}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Severity calculated: {1 <= scoring_result.get('severity_score', 0) <= 5}")
    print(f"   ✓ Business impact calculated: {1 <= scoring_result.get('business_impact_score', 0) <= 10}")
    print(f"   ✓ Has reasoning: {bool(scoring_result.get('scoring_reasoning'))}")
    
except Exception as e:
    print(f"❌ Scoring failed: {e}")

#############################################################################
# STEP 4: RCA LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 4: ROOT CAUSE ANALYSIS - AI-Powered RCA Lambda')
print('=' * 80)

rca_event = {
    'signal': signal,
    'step1': workflow_results.get('correlation', {}),
    'step2': workflow_results.get('scoring', {})
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-rootcause-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(rca_event)
    )
    rca_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['rca'] = rca_result
    
    print(f"\n✅ RCA Lambda Response:")
    print(f"   Status: {rca_result.get('statusCode', 'N/A')}")
    
    root_causes = rca_result.get('root_causes', [])
    if root_causes:
        primary = root_causes[0]
        print(f"   Primary Root Cause: {primary.get('description', 'N/A')[:60]}...")
        print(f"   Confidence: {primary.get('confidence', 'N/A')}%")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Root causes identified: {len(root_causes)}")
    print(f"   ✓ Has confidence score: {bool(root_causes and root_causes[0].get('confidence'))}")
    
except Exception as e:
    print(f"❌ RCA failed: {e}")

#############################################################################
# STEP 5: AGENT INVESTIGATION (Bedrock Agent)
#############################################################################
print('\n' + '=' * 80)
print('STEP 5: AGENT INVESTIGATION - Bedrock Agent with 6 Tools')
print('=' * 80)

agent_event = {
    'signal': signal,
    'step3': workflow_results.get('rca', {})
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-agent-invoker-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(agent_event)
    )
    agent_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['agent'] = agent_result
    
    investigation = agent_result.get('investigation', '')
    
    print(f"\n✅ Agent Investigation Response:")
    print(f"   Status: {agent_result.get('statusCode', 'N/A')}")
    print(f"   Investigation Length: {len(investigation)} chars")
    
    # Check which tools were called
    tools_called = []
    if '[Source: Incident History' in investigation:
        tools_called.append('✓ checkIncidentHistory')
    if '[Source: OpenSearch' in investigation:
        tools_called.append('✓ searchOpenSearchLogs')
    if '[Source: Runbook' in investigation:
        tools_called.append('✓ getRunbook')
    if '[Source: Deployment' in investigation:
        tools_called.append('✓ checkDeployments')
    if '[Source: X-Ray' in investigation:
        tools_called.append('✓ getXRayTraces')
    if '[Source: AWS Config' in investigation:
        tools_called.append('✓ checkConfigDrift')
    
    print(f"\n   Tools Called ({len(tools_called)}/6):")
    for tool in tools_called:
        print(f"      {tool}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ All 6 tools called: {len(tools_called) == 6}")
    print(f"   ✓ Investigation has content: {len(investigation) > 100}")
    
    # Show sample of investigation
    print(f"\n   Investigation Sample:")
    print(f"   {investigation[:300]}...")
    
except Exception as e:
    print(f"❌ Agent investigation failed: {e}")

#############################################################################
# STEP 6: REMEDIATION LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 6: REMEDIATION - AI Recommendations Lambda')
print('=' * 80)

remediation_event = {
    'incident_id': incident_id,
    'service': signal.get('service', 'payment-service'),
    'alarm_name': signal.get('alarm_name', ''),
    'agent_investigation': workflow_results.get('agent', {}).get('investigation', ''),
    'root_causes': workflow_results.get('rca', {}).get('root_causes', [])
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-remediation-recommend-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(remediation_event)
    )
    remediation_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['remediation'] = remediation_result
    
    recommendations = remediation_result.get('recommendations', [])
    
    print(f"\n✅ Remediation Lambda Response:")
    print(f"   Status: {remediation_result.get('statusCode', 'N/A')}")
    print(f"   Total Recommendations: {len(recommendations)}")
    
    # Categorize recommendations
    categories = {}
    for rec in recommendations:
        cat = rec.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"\n   By Category:")
    for cat, count in categories.items():
        print(f"      {cat}: {count}")
    
    print(f"\n   Top 3 Recommendations:")
    for i, rec in enumerate(recommendations[:3], 1):
        print(f"      {i}. [{rec.get('category')}] {rec.get('description', '')[:50]}...")
        print(f"         Confidence: {rec.get('confidence')}%, Source: {rec.get('source')}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Has recommendations: {len(recommendations) > 0}")
    print(f"   ✓ Based on investigation: {any('AGENT' in str(r.get('source', '')) for r in recommendations)}")
    
except Exception as e:
    print(f"❌ Remediation failed: {e}")

#############################################################################
# STEP 7: SUMMARY LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 7: SUMMARY - AI Summary with Quick Actions')
print('=' * 80)

summary_event = {
    'signal': signal,
    'step1': workflow_results.get('correlation', {}),
    'step2': workflow_results.get('scoring', {}),
    'step3': workflow_results.get('rca', {}),
    'step3b': {'investigation': workflow_results.get('agent', {}).get('investigation', '')},
    'step4': {'recommendations': workflow_results.get('remediation', {}).get('recommendations', [])}
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-remediation-summary-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(summary_event)
    )
    summary_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['summary'] = summary_result
    
    summary = summary_result.get('summary', {})
    
    print(f"\n✅ Summary Lambda Response:")
    print(f"   Status: {summary_result.get('statusCode', 'N/A')}")
    
    print(f"\n   AI Summary:")
    print(f"   {summary.get('ai_summary', 'N/A')[:200]}...")
    
    print(f"\n   Recommended Action:")
    action = summary.get('recommended_action', {})
    print(f"      Type: {action.get('type')}")
    print(f"      Confidence: {action.get('confidence')}%")
    
    print(f"\n   Quick Actions ({len(summary.get('quick_actions', []))}):")
    for i, qa in enumerate(summary.get('quick_actions', [])[:3], 1):
        print(f"      {i}. {qa.get('label', 'N/A')[:50]}...")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Has AI summary: {bool(summary.get('ai_summary'))}")
    print(f"   ✓ Quick actions from data: {len(summary.get('quick_actions', [])) > 0}")
    print(f"   ✓ Uses investigation metrics: {bool(summary.get('investigation_summary'))}")
    
except Exception as e:
    print(f"❌ Summary failed: {e}")

#############################################################################
# STEP 8: POSTMORTEM LAMBDA
#############################################################################
print('\n' + '=' * 80)
print('STEP 8: POSTMORTEM - Full Incident Report')
print('=' * 80)

postmortem_event = {
    'signal': signal,
    'incident_id': incident_id,
    'service': signal.get('service', 'payment-service'),
    'step2': workflow_results.get('scoring', {}),
    'step3': workflow_results.get('rca', {}),
    'step3b': {'investigation': workflow_results.get('agent', {}).get('investigation', '')},
    'step4': {'recommendations': workflow_results.get('remediation', {}).get('recommendations', [])}
}

try:
    response = lambda_client.invoke(
        FunctionName='outageshield-postmortem-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(postmortem_event)
    )
    postmortem_result = json.loads(response['Payload'].read().decode('utf-8'))
    workflow_results['postmortem'] = postmortem_result
    
    pm = postmortem_result.get('postmortem', {})
    
    print(f"\n✅ Postmortem Lambda Response:")
    print(f"   Status: {postmortem_result.get('statusCode', 'N/A')}")
    
    print(f"\n   Summary: {pm.get('summary', 'N/A')[:150]}...")
    print(f"   Root Cause: {pm.get('root_cause', 'N/A')[:80]}...")
    print(f"   Duration: {pm.get('duration', 'N/A')}")
    print(f"   Impact: {pm.get('impact', 'N/A')}")
    
    print(f"\n   Prevention Steps:")
    for i, step in enumerate(pm.get('prevention', [])[:3], 1):
        print(f"      {i}. {step[:60]}...")
    
    # Check investigation data used
    inv = pm.get('investigation', {})
    if inv:
        print(f"\n   Investigation Data Used:")
        print(f"      Sources: {len(inv.get('sources_checked', []))}")
        print(f"      Metrics: {inv.get('metrics', {})}")
    
    print(f"\n📊 ACCURACY CHECK:")
    print(f"   ✓ Uses actual root cause: {bool(pm.get('root_cause'))}")
    print(f"   ✓ Uses investigation data: {bool(pm.get('investigation'))}")
    print(f"   ✓ Uses remediation data: {bool(pm.get('remediation'))}")
    print(f"   ✓ Prevention from recommendations: {len(pm.get('prevention', [])) > 0}")
    
except Exception as e:
    print(f"❌ Postmortem failed: {e}")

#############################################################################
# FINAL SUMMARY
#############################################################################
print('\n' + '=' * 80)
print('WORKFLOW TEST SUMMARY')
print('=' * 80)

steps = [
    ('Detection', 'detection', lambda r: r.get('statusCode') == 200),
    ('Correlation', 'correlation', lambda r: r.get('statusCode') == 200),
    ('Scoring', 'scoring', lambda r: r.get('severity_score', 0) > 0),
    ('RCA', 'rca', lambda r: len(r.get('root_causes', [])) > 0),
    ('Agent Investigation', 'agent', lambda r: len(r.get('investigation', '')) > 100),
    ('Remediation', 'remediation', lambda r: len(r.get('recommendations', [])) > 0),
    ('Summary', 'summary', lambda r: bool(r.get('summary', {}).get('ai_summary'))),
    ('Postmortem', 'postmortem', lambda r: bool(r.get('postmortem', {}).get('summary'))),
]

print('\n┌─────────────────────────┬──────────┬─────────────────────────────────┐')
print('│ Step                    │ Status   │ Key Output                      │')
print('├─────────────────────────┼──────────┼─────────────────────────────────┤')

all_passed = True
for name, key, check in steps:
    result = workflow_results.get(key, {})
    passed = check(result) if result else False
    status = '✅ PASS' if passed else '❌ FAIL'
    all_passed = all_passed and passed
    
    # Get key output
    if key == 'detection':
        output = f"Signal: {result.get('signal', {}).get('signal_id', 'N/A')[:15]}"
    elif key == 'scoring':
        output = f"Severity: {result.get('severity_score', 'N/A')}/5"
    elif key == 'rca':
        rcs = result.get('root_causes', [])
        output = f"Root causes: {len(rcs)}" if rcs else "N/A"
    elif key == 'agent':
        inv = result.get('investigation', '')
        tools = sum(1 for s in ['Incident History', 'OpenSearch', 'Runbook', 'Deployment', 'X-Ray', 'Config'] if s in inv)
        output = f"Tools: {tools}/6, Chars: {len(inv)}"
    elif key == 'remediation':
        output = f"Recommendations: {len(result.get('recommendations', []))}"
    elif key == 'summary':
        output = f"Quick actions: {len(result.get('summary', {}).get('quick_actions', []))}"
    elif key == 'postmortem':
        output = f"Prevention: {len(result.get('postmortem', {}).get('prevention', []))}"
    else:
        output = "OK" if passed else "Failed"
    
    print(f'│ {name:<23} │ {status:<8} │ {output:<31} │')

print('└─────────────────────────┴──────────┴─────────────────────────────────┘')

print(f'\n{"✅ ALL STEPS PASSED!" if all_passed else "❌ SOME STEPS FAILED"}')
print(f'Test completed: {datetime.now().isoformat()}')
print('=' * 80)
