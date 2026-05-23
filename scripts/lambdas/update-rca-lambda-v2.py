"""Update RCA Lambda - bulletproof root_cause extraction."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']

def lambda_handler(event, context):
    incident_context = event.get('incident_context', event.get('signal', {}))
    incident_id = incident_context.get('signal_id', incident_context.get('signal', {}).get('signal_id', ''))
    prompt = build_rca_prompt(incident_context)
    response = invoke_bedrock(prompt)
    root_causes = parse_root_causes(response)

    if incident_id and root_causes:
        store_root_cause(incident_id, root_causes)

    return {
        'statusCode': 200,
        'root_causes': root_causes,
        'incident_context_id': incident_context.get('context_id', 'unknown')
    }

def store_root_cause(incident_id, root_causes):
    table = dynamodb.Table(os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev'))
    top = root_causes[0] if root_causes else {}
    description = extract_clean_description(top)
    try:
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET root_cause = :rc, confidence = :c, root_causes_raw = :recs, workflow_step = :ws',
            ExpressionAttributeValues={
                ':rc': description,
                ':c': int(top.get('confidence', 50)),
                ':recs': json.dumps(root_causes, default=str),
                ':ws': 'root_cause_analysis'
            }
        )
    except Exception as e:
        print(f"Store RCA failed: {e}")

def extract_clean_description(item):
    """Always return a clean plain-text description, never JSON."""
    desc = item.get('description', 'Unknown')
    if not isinstance(desc, str):
        desc = str(desc)
    # If it looks like JSON, parse and extract
    stripped = desc.strip()
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list) and parsed:
                if isinstance(parsed[0], dict):
                    return parsed[0].get('description', str(parsed[0])[:150])
                return str(parsed[0])[:150]
            if isinstance(parsed, dict):
                return parsed.get('description', str(parsed)[:150])
        except:
            pass
        # Still looks like JSON but couldn't parse - take first sentence
        for char in ['.', ',', '\\n']:
            if char in stripped[10:]:
                idx = stripped.index(char, 10)
                return stripped[:idx+1] if char == '.' else stripped[:idx]
        return stripped[:150]
    return desc

def build_rca_prompt(context):
    return f"""Analyze this incident and identify the top 3 probable root causes.

IMPORTANT FORMAT RULES:
- Return ONLY a valid JSON array
- Each "description" MUST be a single plain-text sentence (e.g., "Database connection pool exhaustion due to increased load")
- Do NOT put JSON inside the description field
- Keep descriptions under 100 characters

Return format:
[
  {{"description": "short plain text sentence", "confidence": 80, "evidence": "what data supports this"}},
  {{"description": "another plain text sentence", "confidence": 60, "evidence": "supporting data"}}
]

Incident context: {json.dumps(context, default=str)[:2000]}

Return the JSON array only, no other text."""

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

def parse_root_causes(response_text):
    try:
        text = response_text.strip()
        # Remove markdown code fences
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        
        if text.startswith('['):
            causes = json.loads(text)
        else:
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                causes = json.loads(text[start:end])
            else:
                return [{'description': text[:100], 'confidence': 50, 'evidence': 'Could not parse structured response'}]
        
        # Validate and clean each cause
        cleaned = []
        for cause in causes[:3]:
            if isinstance(cause, dict):
                desc = cause.get('description', '')
                # If description is itself a JSON array (double-encoded), unwrap it
                if isinstance(desc, str) and desc.strip().startswith('['):
                    try:
                        inner = json.loads(desc.strip())
                        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                            # Use the inner array instead
                            for inner_cause in inner[:3]:
                                inner_desc = inner_cause.get('description', '')
                                if isinstance(inner_desc, str) and not inner_desc.strip().startswith('['):
                                    cleaned.append({
                                        'description': inner_desc,
                                        'confidence': inner_cause.get('confidence', 50),
                                        'evidence': inner_cause.get('evidence', '')
                                    })
                            break
                    except:
                        pass
                    # Still looks like JSON - skip this entry
                    continue
                if isinstance(desc, str) and not desc.strip().startswith('{') and 'Parse error' not in desc:
                    cleaned.append(cause)
                else:
                    plain = extract_clean_description(cause)
                    if plain and 'Parse error' not in plain:
                        cleaned.append({
                            'description': plain,
                            'confidence': cause.get('confidence', 50),
                            'evidence': cause.get('evidence', '')
                        })
        return cleaned if cleaned else [{'description': response_text[:100], 'confidence': 50, 'evidence': 'Parse fallback'}]
    except Exception as e:
        print(f"Parse error: {e}")
        # Last resort: extract first sentence from response
        text = response_text.strip()[:200]
        if '.' in text[10:]:
            text = text[:text.index('.', 10)+1]
        return [{'description': text[:100], 'confidence': 50, 'evidence': f'Parse error: {str(e)[:50]}'}]

def extract_clean_description(item):
    desc = item.get('description', 'Unknown')
    if not isinstance(desc, str):
        desc = str(desc)
    stripped = desc.strip()
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed[0].get('description', str(parsed[0])[:100])
            if isinstance(parsed, dict):
                return parsed.get('description', str(parsed)[:100])
        except:
            pass
        return stripped[:100]
    return desc
'''

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
zip_buffer.seek(0)

print("Updating RCA Lambda (v2 - bulletproof)...")
r = lambda_client.update_function_code(FunctionName='outageshield-rootcause-dev', ZipFile=zip_buffer.read())
print(f"✓ Updated! Last modified: {r['LastModified']}")
