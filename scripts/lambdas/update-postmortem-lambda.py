"""Update the postmortem Lambda to use existing root cause from previous steps."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
import uuid
from datetime import datetime, timezone

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']

def lambda_handler(event, context):
    # Extract from Step Functions state — all previous steps are available
    signal = event.get('signal', {})
    incident_id = event.get('incident_id') or signal.get('signal_id', '')
    service = event.get('service') or signal.get('service', 'unknown')

    # Get root cause from Step 3
    step3 = event.get('step3', {})
    root_causes = step3.get('root_causes', [])
    root_cause = root_causes[0].get('description', '') if root_causes else ''
    confidence = root_causes[0].get('confidence', 0) if root_causes else 0

    # Get scoring from Step 2
    step2 = event.get('step2', {})
    severity = step2.get('severity_score', signal.get('severity_score', 3))
    affected_users = step2.get('affected_users', 0)
    revenue_at_risk = step2.get('revenue_at_risk', 'Unknown')
    scoring_reasoning = step2.get('scoring_reasoning', '')

    # Get agent investigation from Step 3b
    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '')

    # Get recommendations from Step 4
    step4 = event.get('step4', {})
    recommendations = step4.get('recommendations', [])

    # Build a rich prompt using ALL previous step data
    prompt = f"""Generate a structured incident postmortem for service "{service}".

USE THE FOLLOWING FACTS FROM THE INVESTIGATION (do NOT invent different information):

ROOT CAUSE (from AI analysis, confidence {confidence}%):
{root_cause or 'Unknown - analysis pending'}

SEVERITY: {severity}/5
AFFECTED USERS: {affected_users}
REVENUE AT RISK: {revenue_at_risk}

SCORING REASONING:
{scoring_reasoning or 'Not available'}

AGENT INVESTIGATION FINDINGS:
{agent_investigation[:1500] or 'Agent investigation not available'}

REMEDIATION RECOMMENDATIONS:
{json.dumps(recommendations[:3], default=str)[:1000] if recommendations else 'None available'}

ALARM DETAILS:
{signal.get('source_event_summary', json.dumps(signal, default=str)[:500])}

RULES:
- The "root_cause" field MUST match the root cause above — do NOT invent a different one.
- The "summary" should describe what happened using the facts above.
- The "prevention" steps should be specific to this root cause, not generic.
- The "impact" should use the affected_users and revenue_at_risk numbers above.
- The "duration" should be estimated based on severity.

Return ONLY a JSON object with:
1. "summary" - what happened (2-3 sentences using the facts above)
2. "root_cause" - MUST be: "{root_cause or 'Under investigation'}"
3. "duration" - estimated duration based on severity
4. "prevention" - array of 3 specific prevention steps for THIS root cause
5. "impact" - who was affected (use the numbers above)

Return JSON only."""

    try:
        text = invoke_bedrock(prompt)
        start = text.find('{')
        end = text.rfind('}') + 1
        postmortem_data = json.loads(text[start:end]) if start >= 0 else {}
        # Force root cause to match Step 3
        if root_cause:
            postmortem_data['root_cause'] = root_cause
    except Exception as e:
        print(f"Postmortem generation failed: {e}")
        postmortem_data = {
            'summary': f'Incident on {service}: {root_cause or "Under investigation"}',
            'root_cause': root_cause or 'Analysis pending',
            'prevention': ['Review and address root cause', 'Add monitoring for early detection', 'Update runbooks'],
            'duration': 'Under investigation',
            'impact': f'{affected_users} users affected. Revenue at risk: {revenue_at_risk}'
        }

    # Store in postmortems table
    store_postmortem(incident_id, service, postmortem_data, scoring_reasoning)

    return {'statusCode': 200, 'postmortem': postmortem_data}

def store_postmortem(incident_id, service, data, scoring_reasoning=''):
    if not incident_id:
        return
    table = dynamodb.Table(os.environ['POSTMORTEMS_TABLE'])
    try:
        table.put_item(Item={
            'postmortem_id': 'PM-' + str(uuid.uuid4())[:8],
            'incident_id': incident_id,
            'service': service,
            'title': f"Postmortem: {service} incident",
            'summary': data.get('summary', ''),
            'root_cause': data.get('root_cause', ''),
            'duration': data.get('duration', 'Unknown'),
            'prevention': json.dumps(data.get('prevention', [])),
            'impact_summary': data.get('impact', ''),
            'scoring_reasoning': scoring_reasoning,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'GENERATED'
        })
        print(f"Postmortem stored for {incident_id}")
    except Exception as e:
        print(f"Store postmortem failed: {e}")
    # Also update incident status
    try:
        inc_table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
        inc_table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET workflow_step = :ws, postmortem_generated = :pg',
            ExpressionAttributeValues={':ws': 'postmortem', ':pg': True}
        )
    except Exception:
        pass

def invoke_bedrock(prompt):
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 2048,
            'messages': [{'role': 'user', 'content': prompt}]
        })
    )
    body = json.loads(response['body'].read())
    return body['content'][0]['text']
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating postmortem Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-postmortem-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
