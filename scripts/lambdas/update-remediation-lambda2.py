"""Update the remediation Lambda - smart source injection with negative evidence detection."""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')

LAMBDA_CODE = """
import json
import re
import boto3
import os

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')


def lambda_handler(event, context):
    print(f'Remediation event keys: {list(event.keys())}')
    root_causes = event.get('root_causes', [])
    incident_context = event.get('incident_context', {})
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')

    step3 = event.get('step3', {})
    if not root_causes:
        root_causes = step3.get('root_causes', [])
    if not incident_id:
        incident_id = step3.get('incident_context_id', event.get('incident_id', ''))

    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '')

    print(f'Remediation: incident_id={incident_id}, root_causes={len(root_causes)}, agent={bool(agent_investigation)}')

    prompt = build_remediation_prompt(root_causes, incident_context, agent_investigation)
    response = invoke_bedrock(prompt)
    result = parse_recommendations(response)
    if isinstance(result, tuple):
        _, recommendations = result
    else:
        recommendations = result or []

    recommendations = ensure_all_sources(recommendations, agent_investigation, root_causes)
    summary = generate_summary(root_causes, agent_investigation, recommendations)

    if incident_id and recommendations:
        store_recommendations(incident_id, recommendations, summary)

    return {'statusCode': 200, 'recommendations': recommendations, 'summary': summary}


def store_recommendations(incident_id, recommendations, summary=''):
    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        update_expr = 'SET recommendations_raw = :recs, workflow_step = :ws'
        values = {':recs': json.dumps(recommendations, default=str), ':ws': 'remediation'}
        if summary:
            update_expr += ', remediation_summary = :rs'
            values[':rs'] = summary
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=values
        )
    except Exception as e:
        print(f'Store recommendations failed: {e}')


def ensure_all_sources(recommendations, agent_investigation, root_causes):
    # Inject missing source recommendations ONLY when positive evidence exists.
    # Checks for negative signals (No X found) to avoid false positives.
    existing_sources = {r.get('source', '') for r in recommendations}
    inv = agent_investigation or ''

    def has_positive_evidence(positive_patterns, negative_patterns):
        has_pos = any(re.search(p, inv, re.IGNORECASE | re.DOTALL) for p in positive_patterns)
        has_neg = any(re.search(p, inv, re.IGNORECASE | re.DOTALL) for p in negative_patterns)
        return has_pos and not has_neg

    # AGENT:runbook - only if runbook had actual steps
    if 'AGENT:runbook' not in existing_sources:
        pos = [r'\\[Source:\\s*Runbook', r'runbook.*steps?', r'runbook.*provides?', r'runbook.*contains?', r'runbook.*guidance', r'runbook.*general']
        neg = [r'no runbook.*found', r'no runbook entries', r'runbook.*not found', r'no.*runbook.*data']
        if has_positive_evidence(pos, neg):
            # Extract actual runbook content from agent investigation
            runbook_desc = ''
            runbook_match = re.search(r'\\[Source:\\s*Runbook[^\\]]*\\]\\s*(.+?)(?=\\[Source:|$)', inv, re.IGNORECASE | re.DOTALL)
            if runbook_match:
                runbook_desc = runbook_match.group(1).strip()[:200]
            if not runbook_desc:
                runbook_match2 = re.search(r'runbook for.*?(?:provides?|contains?|suggests?)(.+?)(?:\\.|$)', inv, re.IGNORECASE)
                if runbook_match2:
                    runbook_desc = runbook_match2.group(0).strip()[:200]
            if not runbook_desc:
                runbook_desc = 'Follow the runbook steps: review CloudWatch metrics for resource spikes, check recent deployments, review application logs for error patterns'
            recommendations.append({
                'category': 'manual_intervention',
                'description': runbook_desc,
                'reasoning': 'The runbook for this alarm type provides troubleshooting steps that should be followed as part of the incident response.',
                'source': 'AGENT:runbook',
                'effectiveness': 3, 'risk': 'low', 'estimated_ttr_minutes': 90, 'confidence': 75
            })

    # AGENT:log_patterns - only if OpenSearch returned actual alarm data
    if 'AGENT:log_patterns' not in existing_sources:
        pos = [r'\\[Source:\\s*OpenSearch', r'alarm.*found', r'alarms.*show', r'log.*show', r'5xx|latency|timeout|error rate|CPU|memory|disk|health check|queue']
        neg = [r'no.*log.*found', r'no.*alarm.*found', r'no.*opensearch.*found', r'no.*log.*patterns.*found']
        if has_positive_evidence(pos, neg):
            # Extract actual OpenSearch findings from agent investigation
            log_desc = ''
            log_match = re.search(r'\\[Source:\\s*OpenSearch[^\\]]*\\]\\s*(.+?)(?=\\[Source:|$)', inv, re.IGNORECASE | re.DOTALL)
            if log_match:
                log_desc = log_match.group(1).strip()[:200]
            if not log_desc:
                log_desc = 'Investigate the specific error patterns found in OpenSearch logs to identify the affected endpoints and correlate with the root cause.'
            recommendations.append({
                'category': 'manual_intervention',
                'description': log_desc,
                'reasoning': 'OpenSearch logs revealed high-severity alarms indicating performance degradation.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 3, 'risk': 'low', 'estimated_ttr_minutes': 120, 'confidence': 80
            })

    # AGENT:past_incidents - only if actual past incidents were found
    if 'AGENT:past_incidents' not in existing_sources:
        pos = [r'\\[Source:\\s*Incident History', r'past incidents?.*found', r'similar incidents?.*found', r'\\d+\\s+(?:similar\\s+)?past incidents?']
        neg = [r'no similar past incidents', r'no past incidents.*found', r'no.*similar.*incidents.*found', r'0 past incidents']
        if has_positive_evidence(pos, neg):
            recommendations.append({
                'category': 'manual_intervention',
                'description': 'Apply the same fix that resolved similar past incidents on this service: rollback recent deployment changes and scale up resources.',
                'reasoning': 'Past incident history shows a consistent pattern of this type of failure with known resolutions.',
                'source': 'AGENT:past_incidents',
                'effectiveness': 4, 'risk': 'medium', 'estimated_ttr_minutes': 60, 'confidence': 85
            })

    # AGENT:deployment_correlation - only if actual deployment was found
    if 'AGENT:deployment_correlation' not in existing_sources:
        pos = [r'recent deployment.*found', r'deployment.*correlat', r'deploy.*version.*\\d', r'config.*change.*found', r'deploy-\\w+-\\d+', r'updated the connection pool', r'deployment on \\d{4}']
        neg = [r'no recent deployments', r'no.*deployment.*found', r'no.*config.*change.*found', r'no deployments', r'no information available about recent deploy']
        if has_positive_evidence(pos, neg):
            recommendations.append({
                'category': 'rollback',
                'description': 'Rollback the recent deployment that changed the service configuration, as it correlates with the start of the incident.',
                'reasoning': 'Deployment history shows a recent change that correlates with the incident timeline.',
                'source': 'AGENT:deployment_correlation',
                'effectiveness': 5, 'risk': 'medium', 'estimated_ttr_minutes': 30, 'confidence': 80
            })

    return sorted(recommendations, key=lambda x: x.get('effectiveness', 0), reverse=True)[:6]


def generate_summary(root_causes, agent_investigation, recommendations):
    inv = agent_investigation or ''

    # Count past incidents
    past_count = re.search(r'(\d+)\s+(?:similar\s+)?past incidents?', inv, re.IGNORECASE)

    # Detect evidence
    has_logs = bool(re.search(r'OpenSearch|alarm|5xx|latency|timeout|error rate|CPU|memory|health check|queue', inv, re.IGNORECASE))
    has_deploy = bool(re.search(r'deployment.*correlat|recent deployment.*found|deploy-\w+-\d+|updated the connection pool|deployment on \d{4}', inv, re.IGNORECASE))
    no_deploy = bool(re.search(r'no recent deployments|no.*deployment.*found|no information available about recent', inv, re.IGNORECASE))
    has_runbook = bool(re.search(r'runbook.*steps|runbook.*provides|runbook.*general|\[Source:\s*Runbook', inv, re.IGNORECASE | re.DOTALL))

    # Get root cause
    rc_desc = ''
    if root_causes:
        rc_desc = root_causes[0].get('description', '') if isinstance(root_causes[0], dict) else str(root_causes[0])

    # Categorize recommendations by type
    recs = recommendations or []
    rollbacks = [r for r in recs if r.get('category') == 'rollback']
    scaling = [r for r in recs if r.get('category') == 'scaling']
    config_changes = [r for r in recs if r.get('category') == 'configuration_change']
    manual = [r for r in recs if r.get('category') == 'manual_intervention']

    if not recs and not rc_desc:
        return ''

    # Build SRE-friendly paragraph
    paragraph = ''

    # Opening: what happened
    if rc_desc:
        rc_clean = rc_desc.rstrip('.')
        paragraph += f'Root cause: {rc_clean}. '

    # What evidence supports this
    evidence = []
    if past_count:
        evidence.append(f'{past_count.group(1)} similar past incidents confirm this pattern')
    if has_logs:
        evidence.append('OpenSearch logs show active alarms')
    if has_deploy and not no_deploy:
        evidence.append('a recent deployment correlates with the incident start')
    if evidence:
        paragraph += f'Evidence: {", ".join(evidence)}. '

    # Action plan: what to do NOW
    paragraph += 'Action plan: '
    actions = []
    if rollbacks:
        desc = rollbacks[0].get('description', '').rstrip('.')
        if len(desc) > 100:
            desc = desc[:100].rsplit(' ', 1)[0]
        actions.append(f'(1) {desc}')
    if scaling:
        desc = scaling[0].get('description', '').rstrip('.')
        if len(desc) > 100:
            desc = desc[:100].rsplit(' ', 1)[0]
        actions.append(f'({"2" if rollbacks else "1"}) {desc}')
    if config_changes:
        desc = config_changes[0].get('description', '').rstrip('.')
        if len(desc) > 100:
            desc = desc[:100].rsplit(' ', 1)[0]
        n = 1 + len([x for x in [rollbacks, scaling] if x])
        actions.append(f'({n}) {desc}')
    if manual and len(actions) < 3:
        desc = manual[0].get('description', '').rstrip('.')
        if len(desc) > 100:
            desc = desc[:100].rsplit(' ', 1)[0]
        n = len(actions) + 1
        actions.append(f'({n}) {desc}')

    if actions:
        paragraph += '; '.join(actions) + '.'
    else:
        paragraph += 'Manual investigation required.'

    # Runbook note
    if has_runbook:
        paragraph += ' Runbook available for reference.'

    return paragraph


def build_remediation_prompt(root_causes, context, agent_investigation):
    prompt = (
        'You are a Site Reliability Engineer generating remediation recommendations.\\n\\n'
        'SOURCE ATTRIBUTION RULES:\\n'
        '- AGENT:runbook              = runbook steps were found (even general ones)\\n'
        '- AGENT:past_incidents       = past incidents were found with known fixes\\n'
        '- AGENT:deployment_correlation = a specific deployment/config change was identified\\n'
        '- AGENT:log_patterns         = specific error patterns were found in OpenSearch logs\\n'
        '- RCA                        = recommendation comes from root cause analysis\\n'
        '- agent_advice               = general advice with NO tool data supporting it\\n\\n'
        'CRITICAL: If the agent says "No X found" or "No similar past incidents" or "No recent deployments"\\n'
        '- Do NOT use that source. Use RCA or agent_advice instead.\\n'
        '- Only use a source if the tool ACTUALLY returned useful data.\\n\\n'
        f'EVIDENCE SOURCE 1 - ROOT CAUSE ANALYSIS:\\n{json.dumps(root_causes)}\\n\\n'
        f'SERVICE: {context.get("service", "unknown")}\\n'
    )

    if agent_investigation:
        prompt += f'\\nEVIDENCE SOURCE 2 - BEDROCK AGENT INVESTIGATION:\\n{agent_investigation[:3000]}\\n'
    else:
        prompt += '\\nEVIDENCE SOURCE 2 - AGENT INVESTIGATION: Not available. Set max confidence to 60.\\n'

    prompt += (
        '\\nOUTPUT: Return a JSON array of up to 4 recommendations ranked by effectiveness. Each object MUST have:\\n'
        '- category: rollback | scaling | configuration_change | manual_intervention\\n'
        '- description: specific action (not vague)\\n'
        '- reasoning: cite which evidence source supports this\\n'
        '- source: one of the source values listed above\\n'
        '- effectiveness: 1-5\\n'
        '- risk: low | medium | high\\n'
        '- estimated_ttr_minutes: integer\\n'
        '- confidence: 0-100\\n\\n'
        'Return JSON array only, no other text.'
    )
    return prompt


def invoke_bedrock(prompt):
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 4096,
            'messages': [{'role': 'user', 'content': prompt}]
        })
    )
    body = json.loads(response['body'].read())
    return body['content'][0]['text']


def parse_recommendations(response_text):
    try:
        text = response_text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        if text.startswith('{'):
            obj = json.loads(text)
            recs = obj.get('recommendations', [])
        elif text.startswith('['):
            recs = json.loads(text)
        else:
            arr_start = text.find('[')
            arr_end = text.rfind(']') + 1
            if arr_start >= 0 and arr_end > arr_start:
                recs = json.loads(text[arr_start:arr_end])
            else:
                raise ValueError('No JSON array found')
        valid_cats = ('rollback', 'scaling', 'configuration_change', 'manual_intervention')
        valid = [r for r in recs if r.get('category') in valid_cats]
        recs = valid if valid else recs
        return '', sorted(recs, key=lambda x: x.get('effectiveness', 0), reverse=True)[:4]
    except (json.JSONDecodeError, ValueError) as e:
        print(f'Parse error: {e} | Raw: {response_text[:300]}')
        return '', [{
            'category': 'manual_intervention',
            'description': 'AI recommendation parsing failed. Manual review required.',
            'reasoning': f'Parse error: {str(e)[:100]}',
            'source': 'insufficient_evidence',
            'effectiveness': 1, 'risk': 'medium', 'estimated_ttr_minutes': 30, 'confidence': 20
        }]
"""

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', LAMBDA_CODE.lstrip())
zip_buffer.seek(0)

print("Updating remediation-recommend Lambda...")
r = lambda_client.update_function_code(
    FunctionName='outageshield-remediation-recommend-dev',
    ZipFile=zip_buffer.read()
)
print(f"Updated! Last modified: {r['LastModified']}")
