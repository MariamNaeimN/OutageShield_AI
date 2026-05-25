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
    Also convert XML-style section tags to [Source: X] format for consistent parsing.
    Aggressively truncate anything after Deployment History findings."""
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
    # Remove 'Recommended Actions:' section and everything after
    text = re.sub(r'\s*[Rr]ecommended [Aa]ctions?:[\s\S]*$', '', text).strip()
    # Remove 'Next Steps:' section and everything after
    text = re.sub(r'\s*[Nn]ext [Ss]teps?:[\s\S]*$', '', text).strip()
    # Remove 'Summary:' section at the end
    text = re.sub(r'\s*[Ss]ummary:[\s\S]*$', '', text).strip()
    # Remove 'In summary' or 'To summarize' conclusions
    text = re.sub(r'\s*[Ii]n summary[\s\S]*$', '', text).strip()
    text = re.sub(r'\s*[Tt]o summarize[\s\S]*$', '', text).strip()
    # Remove 'Based on the findings' conclusions
    text = re.sub(r'\s*[Bb]ased on the (findings|investigation)[\s\S]*$', '', text).strip()
    # Remove 'This concludes' endings
    text = re.sub(r'\s*[Tt]his concludes[\s\S]*$', '', text).strip()
    # Remove 'I have completed/provided/finished' endings
    text = re.sub(r'\s*I have (now )?(completed|provided|finished)[\s\S]*$', '', text).strip()
    return text

def lambda_handler(event, context):
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    service = signal.get('service', 'unknown')
    alarm_name = signal.get('alarm_name', '')

    step3 = event.get('step3', {})
    root_causes = step3.get('root_causes', [])
    root_cause = root_causes[0].get('description', 'Unknown') if root_causes else 'Unknown'

    prompt = f"""You are an incident investigation agent.
Your task is to perform a structured investigation ONLY.
You MUST NOT include any remediation, recommendations, summaries, or next steps.

STRICT OUTPUT RULES:
- You MUST include ALL 4 source sections in your output, even if a tool returns no data.
- Do NOT skip any section. If a tool returns no data, write "No relevant data found" for that section.
- Do NOT add any extra sections.
- Do NOT include "Remediation Summary", "Recommended Actions", "Next Steps", or similar content.
- Your response MUST end immediately after the Deployment History findings.
- Any content after Deployment History findings is INVALID.

REQUIRED TOOL EXECUTION ORDER (DO NOT SKIP ANY):
1) searchIncidentHistory → report under [Source: Incident History DB]
2) searchLogs (time_range=6h) → report under [Source: OpenSearch Logs]
3) getRunbook → report under [Source: Runbook DB]
4) checkDeployments → report under [Source: Deployment History]

OUTPUT FORMAT (STRICT - ALL 4 SECTIONS REQUIRED):
[Source: Incident History DB]
<findings or "No relevant data found">

[Source: OpenSearch Logs]
<findings or "No relevant data found">

[Source: Runbook DB]
<findings or "No relevant data found">

[Source: Deployment History]
<findings or "No relevant data found">

CRITICAL RULES:
- You MUST call ALL 4 tools and include ALL 4 sections.
- STOP WRITING immediately after Deployment History section.
- Do NOT explain, summarize, or conclude.
- Do NOT generate remediation under any form.
- Do NOT skip sections even if they have no data.

Context:
- Service: {service}
- Alarm: {alarm_name}
- Initial suspected root cause: {root_cause}"""

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
