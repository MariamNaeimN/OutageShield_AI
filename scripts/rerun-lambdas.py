"""
Rerun scoring, remediation, and summary Lambdas for specific incidents.
"""
import boto3
import json
import sys

lambda_client = boto3.client('lambda', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Default incidents - can be overridden by command line args
DEFAULT_INCIDENTS = ['INC-2B3885E0', 'INC-B2F8A87F']

def get_all_incidents():
    """Fetch all incident IDs from DynamoDB."""
    table = dynamodb.Table('outageshield-incidents-dev')
    response = table.scan(ProjectionExpression='incident_id')
    incidents = [item['incident_id'] for item in response.get('Items', [])]
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            ProjectionExpression='incident_id',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        incidents.extend([item['incident_id'] for item in response.get('Items', [])])
    return incidents

def get_incident(incident_id):
    """Fetch incident from DynamoDB."""
    table = dynamodb.Table('outageshield-incidents-dev')
    response = table.get_item(Key={'incident_id': incident_id})
    return response.get('Item', {})

def invoke_lambda(function_name, payload):
    """Invoke a Lambda function."""
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    result = json.loads(response['Payload'].read())
    return result

def rerun_for_incident(incident_id):
    """Rerun scoring, remediation, and summary for an incident."""
    print(f"\n{'='*60}")
    print(f"Processing: {incident_id}")
    print('='*60)
    
    # Get incident data
    incident = get_incident(incident_id)
    if not incident:
        print(f"  ❌ Incident not found: {incident_id}")
        return
    
    service = incident.get('service', 'unknown')
    alarm_name = incident.get('alarm_name', '')
    context = incident.get('context', '{}')
    agent_investigation = incident.get('agent_investigation', '')
    root_causes_raw = incident.get('root_causes_raw', '[]')
    
    print(f"  Service: {service}")
    print(f"  Alarm: {alarm_name}")
    
    # Parse context
    try:
        incident_context = json.loads(context) if isinstance(context, str) else context
    except:
        incident_context = {'service': service, 'alarm_name': alarm_name}
    
    # Parse root causes
    try:
        root_causes = json.loads(root_causes_raw) if isinstance(root_causes_raw, str) else root_causes_raw
    except:
        root_causes = []
    
    # 1. Rerun Scoring Lambda
    print(f"\n  1️⃣ Running Scoring Lambda...")
    scoring_payload = {
        'incident_context': incident_context,
        'signal': {
            'signal_id': incident_id,
            'service': service,
            'alarm_name': alarm_name
        }
    }
    try:
        scoring_result = invoke_lambda('outageshield-scoring-dev', scoring_payload)
        print(f"     ✅ Severity: {scoring_result.get('severity_score')}")
        print(f"     ✅ Business Impact: {scoring_result.get('business_impact_score')}")
        print(f"     ✅ Affected Users: {scoring_result.get('affected_users')}")
        print(f"     ✅ Revenue at Risk: {scoring_result.get('revenue_at_risk')}")
    except Exception as e:
        print(f"     ❌ Scoring failed: {e}")
        scoring_result = {}
    
    # 2. Rerun Remediation Lambda
    print(f"\n  2️⃣ Running Remediation Lambda...")
    remediation_payload = {
        'incident_id': incident_id,
        'service': service,
        'alarm_name': alarm_name,
        'root_causes': root_causes,
        'incident_context': incident_context,
        'signal': {'signal_id': incident_id, 'service': service},
        'step3b': {'investigation': agent_investigation}
    }
    try:
        remediation_result = invoke_lambda('outageshield-remediation-recommend-dev', remediation_payload)
        recommendations = remediation_result.get('recommendations', [])
        print(f"     ✅ Generated {len(recommendations)} recommendations")
        for i, rec in enumerate(recommendations[:3]):
            print(f"        #{i+1}: [{rec.get('category')}] {rec.get('description', '')[:60]}...")
    except Exception as e:
        print(f"     ❌ Remediation failed: {e}")
        remediation_result = {'recommendations': []}
    
    # 3. Rerun Summary Lambda
    print(f"\n  3️⃣ Running Summary Lambda...")
    summary_payload = {
        'signal': {
            'signal_id': incident_id,
            'service': service,
            'alarm_name': alarm_name
        },
        'step1': {'incident_context': incident_context},
        'step2': scoring_result,
        'step3': {'root_causes': root_causes},
        'step3b': {'investigation': agent_investigation},
        'step4': remediation_result
    }
    try:
        summary_result = invoke_lambda('outageshield-remediation-summary-dev', summary_payload)
        summary = summary_result.get('summary', {})
        print(f"     ✅ AI Summary generated")
        print(f"     ✅ Quick Actions: {len(summary.get('quick_actions', []))}")
        ai_summary = summary.get('ai_summary', '')[:200]
        print(f"     📝 Summary: {ai_summary}...")
    except Exception as e:
        print(f"     ❌ Summary failed: {e}")
    
    # 4. Rerun Postmortem Lambda
    print(f"\n  4️⃣ Running Postmortem Lambda...")
    postmortem_payload = {
        'incident_id': incident_id,
        'service': service,
        'alarm_name': alarm_name,
        'root_causes': root_causes,
        'incident_context': incident_context,
        'signal': {'signal_id': incident_id, 'service': service},
        'step2': scoring_result,
        'step3': {'root_causes': root_causes},
        'step3b': {'investigation': agent_investigation},
        'step4': remediation_result
    }
    try:
        postmortem_result = invoke_lambda('outageshield-postmortem-dev', postmortem_payload)
        postmortem = postmortem_result.get('postmortem', {})
        print(f"     ✅ Postmortem generated")
        print(f"     📝 Title: {postmortem.get('title', 'N/A')[:60]}...")
    except Exception as e:
        print(f"     ❌ Postmortem failed: {e}")
    
    print(f"\n  ✅ Completed processing {incident_id}")

def main():
    # Check for --all flag or specific incident IDs
    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            incidents = get_all_incidents()
            print(f"Processing ALL {len(incidents)} incidents...")
        else:
            incidents = sys.argv[1:]
            print(f"Processing {len(incidents)} specified incidents...")
    else:
        incidents = DEFAULT_INCIDENTS
        print(f"Processing default incidents: {incidents}")
    
    print("="*60)
    print("Rerunning Lambdas for Incidents")
    print("="*60)
    print(f"Total incidents: {len(incidents)}")
    print(f"Lambdas: scoring, remediation, summary, postmortem")
    
    success_count = 0
    error_count = 0
    
    for i, incident_id in enumerate(incidents):
        print(f"\n[{i+1}/{len(incidents)}] ", end="")
        try:
            rerun_for_incident(incident_id)
            success_count += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"Done! Processed {len(incidents)} incidents.")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Errors: {error_count}")
    print("="*60)

if __name__ == '__main__':
    main()
