"""Update the remediation Lambda to store recommendations in DynamoDB."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')

def lambda_handler(event, context):
    print(f"Remediation event keys: {list(event.keys())}")
    root_causes = event.get('root_causes', [])
    incident_context = event.get('incident_context', {})
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')

    # Fallback: try step3 output for root causes and incident_id
    step3 = event.get('step3', {})
    if not root_causes:
        root_causes = step3.get('root_causes', [])
    if not incident_id:
        incident_id = step3.get('incident_context_id', event.get('incident_id', ''))

    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '')

    print(f"Remediation: incident_id={incident_id}, root_causes={len(root_causes)}, agent={bool(agent_investigation)}")

    prompt = build_remediation_prompt(root_causes, incident_context, agent_investigation)
    response = invoke_bedrock(prompt)
    recommendations = parse_recommendations(response)

    # Store recommendations in DynamoDB
    if incident_id and recommendations:
        store_recommendations(incident_id, recommendations)

    return {
        'statusCode': 200,
        'recommendations': recommendations
    }

def store_recommendations(incident_id, recommendations):
    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET recommendations_raw = :recs, workflow_step = :ws',
            ExpressionAttributeValues={
                ':recs': json.dumps(recommendations, default=str),
                ':ws': 'remediation'
            }
        )
    except Exception as e:
        print(f"Store recommendations failed: {e}")

def build_remediation_prompt(root_causes, context, agent_investigation):
    prompt = f"""You are a Site Reliability Engineer generating remediation recommendations.

STRICT RULES — ZERO HALLUCINATION:
- You may ONLY recommend actions that are DIRECTLY supported by evidence below.
- Do NOT invent, assume, or fabricate any information not explicitly stated in the evidence.
- If the evidence is insufficient for a specific recommendation, use category "manual_intervention".
- Every recommendation MUST cite its exact source: "RCA" (root cause analysis), "AGENT" (agent investigation), or "RUNBOOK" (runbook match).
- If the agent investigation found a runbook, use the runbook steps as your recommendations.
- If the agent investigation found past incidents with known fixes, recommend those same fixes.
- If the agent investigation found a deployment correlation, recommend rollback.
- Do NOT generate generic advice like "monitor logs" or "check metrics" unless the evidence specifically says to.
- Confidence score MUST reflect evidence strength: 90+ only if runbook match or 3+ similar past incidents confirm it.

EVIDENCE SOURCE 1 — ROOT CAUSE ANALYSIS (Step 3):
{json.dumps(root_causes)}

SERVICE: {context.get('service', 'unknown')}
"""

    if agent_investigation:
        prompt += f"""
EVIDENCE SOURCE 2 — BEDROCK AGENT AUTONOMOUS INVESTIGATION (Step 3b):
The agent searched: past incidents, OpenSearch logs, runbooks, and deployment history.
Results:
{agent_investigation[:3000]}
"""
    else:
        prompt += """
EVIDENCE SOURCE 2 — AGENT INVESTIGATION: Not available (agent was skipped or failed).
Without agent evidence, set max confidence to 60 and recommend manual_intervention as first option.
"""

    prompt += """
OUTPUT FORMAT — Return a JSON array. Each object MUST have:
1. "category": one of (rollback, scaling, configuration_change, manual_intervention)
2. "description": specific action to take (not vague)
3. "reasoning": WHY — cite which evidence source supports this
4. "source": which evidence this came from — one of ("RCA", "AGENT:runbook", "AGENT:past_incidents", "AGENT:deployment_correlation", "AGENT:log_patterns", "insufficient_evidence")
5. "effectiveness": score 1-5 (5 only if runbook or past incident confirms it works)
6. "risk": (low, medium, high)
7. "estimated_ttr_minutes": integer
8. "confidence": 0-100 (90+ requires runbook match or 3+ past incidents; 70-89 requires deployment correlation; below 70 for inference only)

Return as a JSON array ranked by effectiveness. Maximum 4 recommendations.
If evidence is truly insufficient, return: [{"category": "manual_intervention", "description": "Insufficient evidence for automated recommendation. Escalate to service owner.", "reasoning": "No runbook match, no similar past incidents, no deployment correlation found.", "source": "insufficient_evidence", "effectiveness": 1, "risk": "low", "estimated_ttr_minutes": 30, "confidence": 20}]"""

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
        # Remove markdown code fences if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        
        if text.startswith('['):
            recs = json.loads(text)
        else:
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                recs = json.loads(text[start:end])
            else:
                raise ValueError("No JSON array found")
        # Validate each rec has a category
        valid_recs = [r for r in recs if r.get('category') in ('rollback', 'scaling', 'configuration_change', 'manual_intervention')]
        if valid_recs:
            return sorted(valid_recs, key=lambda x: x.get('effectiveness', 0), reverse=True)[:4]
        return sorted(recs, key=lambda x: x.get('effectiveness', 0), reverse=True)[:4]
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Parse error: {e}")
        print(f"Raw text (first 300): {response_text[:300]}")
        return [{'category': 'manual_intervention', 'description': 'AI recommendation parsing failed. Manual review required.',
                 'reasoning': f'Parse error: {str(e)[:100]}',
                 'source': 'insufficient_evidence',
                 'effectiveness': 1, 'risk': 'medium', 'estimated_ttr_minutes': 30,
                 'confidence': 20}]
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating remediation-recommend Lambda...")
r = lambda_client.update_function_code(FunctionName='outageshield-remediation-recommend-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
