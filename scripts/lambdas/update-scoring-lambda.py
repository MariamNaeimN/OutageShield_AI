"""Update scoring Lambda with explicit revenue amounts."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']
INCIDENTS_TABLE = os.environ['INCIDENTS_TABLE']

def lambda_handler(event, context):
    incident_context = event.get('incident_context', event.get('signal', {}))
    incident_id = incident_context.get('signal_id', incident_context.get('signal', {}).get('signal_id', ''))
    service = incident_context.get('service', 'unknown')

    prompt = f"""You are a senior SRE at an e-commerce company doing $500M annual revenue ($57,000/hour average).
Assess the business impact of this incident on service "{service}".

THINK STEP BY STEP:
1. What does this service do? (payment processing? internal logging? user-facing search?)
2. How many users interact with it per hour? (payments = millions, internal tools = 0)
3. What percentage of revenue flows through it? (payments = 60%, search = 5%, logging = 0%)
4. What's the blast radius? (gateway down = everything down, logger down = no customer impact)

EXAMPLES OF CORRECT SCORING:
- payments-api with HighLatency: impact=9, users=1200000, revenue="$34,200/hour (60% of hourly revenue)", sla="Breached"
- orders-service with High5xxRate: impact=8, users=800000, revenue="$22,800/hour (40% of orders affected)", sla="At Risk"
- search-service with HighLatency: impact=6, users=200000, revenue="$2,850/hour (5% revenue from search)", sla="Warning"
- notifications-svc with QueueDepth: impact=4, users=50000, revenue="$570/hour (delayed notifications)", sla="Warning"
- audit-logger with DiskUsage: impact=2, users=0, revenue="$0 (internal only)", sla="OK"
- cache-manager with HighCPU: impact=2, users=0, revenue="$0 (infrastructure)", sla="OK"
- queue-processor with MemoryPressure: impact=1, users=0, revenue="$0 (background processing)", sla="OK"

RULES:
- revenue_at_risk MUST be a specific dollar amount with explanation (e.g., "$12,500/hour (based on 22% of transaction volume)")
- affected_users MUST be 0 for internal/infrastructure services
- sla_status: "Breached" only for impact 9-10, "At Risk" for 7-8, "Warning" for 4-6, "OK" for 1-3
- DO NOT use generic values like "$X/hour" or "Significant" — always calculate a specific number

Context: {json.dumps(incident_context, default=str)[:1200]}

Return ONLY a JSON object:
{{"severity_score": int, "business_impact_score": int, "affected_users": int, "revenue_at_risk": "string with dollar amount and explanation", "sla_status": "string", "service_risk_score": int, "reasoning": "string"}}"""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 512,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        body = json.loads(response['body'].read())
        text = body['content'][0]['text']
        start = text.find('{')
        end = text.rfind('}') + 1
        result = json.loads(text[start:end]) if start >= 0 else {}
        scores = {
            'severity_score': int(result.get('severity_score', 3)),
            'business_impact_score': int(result.get('business_impact_score', 5)),
            'affected_users': int(result.get('affected_users', 0)),
            'revenue_at_risk': str(result.get('revenue_at_risk', 'Unknown')),
            'sla_status': result.get('sla_status', 'Unknown'),
            'service_risk_score': int(result.get('service_risk_score', 50)),
            'scoring_reasoning': result.get('reasoning', '')
        }
    except Exception as e:
        print(f"Scoring error: {e}")
        scores = {'severity_score': 3, 'business_impact_score': 5, 'affected_users': 0, 'revenue_at_risk': 'Unknown', 'sla_status': 'Unknown', 'service_risk_score': 50, 'scoring_reasoning': ''}

    if incident_id:
        store_scores(incident_id, scores)

    return {'statusCode': 200, **scores, 'partial': False}

def store_scores(incident_id, scores):
    table = dynamodb.Table(INCIDENTS_TABLE)
    try:
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET severity_score = :s, business_impact_score = :b, affected_users = :au, revenue_at_risk = :r, sla_status = :sla, service_risk_score = :srs, scoring_reasoning = :sr, workflow_step = :ws',
            ExpressionAttributeValues={
                ':s': scores['severity_score'],
                ':b': scores['business_impact_score'],
                ':au': scores['affected_users'],
                ':r': scores['revenue_at_risk'],
                ':sla': scores['sla_status'],
                ':srs': scores['service_risk_score'],
                ':sr': scores.get('scoring_reasoning', ''),
                ':ws': 'scoring'
            }
        )
    except Exception as e:
        print(f"Store scores failed: {e}")
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating scoring Lambda (hardcoded revenue)...")
r = lambda_client.update_function_code(FunctionName='outageshield-scoring-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
