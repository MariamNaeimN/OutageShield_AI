"""Update agent-invoker Lambda to strip Remediation Summary bleed and increase storage limit."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = r'''import json
import boto3
import os
import uuid
import re

bedrock_agent = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')

AGENT_ID = os.environ.get('AGENT_ID', '')
AGENT_ALIAS_ID = os.environ.get('AGENT_ALIAS_ID', 'TSTALIASID')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')

def clean_investigation(text):
    """Strip trailing Remediation Summary / recommended_actions sections.
    Also convert XML-style section tags to [Source: X] format for consistent parsing."""
    import re
    # Convert XML section tags to [Source: X] markers
    text = re.sub(r'<investigation_summary>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</investigation_summary>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<similar_incidents>', '\n[Source: Incident History DB]\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</similar_incidents>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<log_findings>', '\n[Source: OpenSearch Logs]\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</log_findings>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<deployment_correlation>', '\n[Source: Deployment History]\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</deployment_correlation>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<runbook_findings>', '\n[Source: Runbook DB]\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</runbook_findings>', '', text, flags=re.IGNORECASE)
    # Strip recommended_actions block entirely
    text = re.sub(r'<recommended_actions>[\s\S]*?</recommended_actions>', '', text, flags=re.IGNORECASE)
    # Strip any remaining unknown XML tags
    text = re.sub(r'</?[a-z_]+>', '', text)
    # Remove from 'Remediation Summary:' onwards
    text = re.sub(r'\s*[Rr]emediation[_ ][Ss]ummary:[\s\S]*$', '', text).strip()
    # Remove trailing 'recommended_actions:' block if present
    text = re.sub(r'\s*recommended_actions:[\s\S]*$', '', text).strip()
    return text

def lambda_handler(event, context):
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    service = signal.get('service', 'unknown')
    alarm_name = signal.get('alarm_name', '')

    step3 = event.get('step3', {})
    root_causes = step3.get('root_causes', [])
    root_cause = root_causes[0].get('description', 'Unknown') if root_causes else 'Unknown'

    prompt = (
        f"Investigate the incident on service {service}. "
        f"The alarm is {alarm_name}. "
        f"Initial root cause analysis suggests: {root_cause}. "
        f"Search for similar past incidents, check logs, look up the runbook, "
        f"and check recent deployments. Provide a full investigation summary. "
        f"IMPORTANT: Do NOT include a 'Remediation Summary' section or 'recommended_actions' — "
        f"stop after the deployment correlation findings."
    )

    try:
        response = bedrock_agent.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=str(uuid.uuid4()),
            inputText=prompt
        )

        completion = ''
        for event_stream in response.get('completion', []):
            if 'chunk' in event_stream:
                chunk = event_stream['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')

        # Strip Remediation Summary bleed before storing
        completion = clean_investigation(completion)
        print(f"Agent investigation complete for {incident_id}: {len(completion)} chars")

        table = dynamodb.Table(INCIDENTS_TABLE)
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET agent_investigation = :ai',
            ExpressionAttributeValues={':ai': completion[:3000]}
        )

        return {
            'statusCode': 200,
            'incident_id': incident_id,
            'investigation': completion[:3000],
            'status': 'completed'
        }

    except Exception as e:
        print(f"Agent invocation failed: {e}")
        return {
            'statusCode': 200,
            'incident_id': incident_id,
            'investigation': f'Agent investigation skipped: {str(e)[:100]}',
            'status': 'skipped'
        }
'''

buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
buf.seek(0)

print("Updating agent-invoker Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-invoker-dev', ZipFile=buf.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
