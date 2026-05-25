"""
Update the remediation Lambda to use Bedrock AI for smarter recommendations.
Generates recommendations from ALL agent investigation sources with anti-hallucination rules.
"""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')

LAMBDA_CODE = r'''
import json
import re
import boto3
import os

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')


def lambda_handler(event, context):
    """Main handler - generates AI-powered remediation recommendations."""
    print(f'Remediation event keys: {list(event.keys())}')
    
    # Extract data from various event formats
    root_causes = event.get('root_causes', [])
    incident_context = event.get('incident_context', {})
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    
    # Try step3 format
    step3 = event.get('step3', {})
    if not root_causes:
        root_causes = step3.get('root_causes', [])
    if not incident_id:
        incident_id = step3.get('incident_context_id', event.get('incident_id', ''))
    
    # Get agent investigation from step3b or direct
    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '') or event.get('agent_investigation', '')
    
    # Get service name and alarm
    service = incident_context.get('service') or event.get('service', 'unknown')
    alarm_name = incident_context.get('alarm_name') or event.get('alarm_name', '')
    
    print(f'Remediation: incident_id={incident_id}, service={service}, root_causes={len(root_causes)}, agent_inv_len={len(agent_investigation)}')
    
    # Parse investigation sources
    sources = parse_investigation_sources(agent_investigation)
    print(f'Parsed sources: opensearch={len(sources.get("opensearch",""))}, runbook={len(sources.get("runbook",""))}, deployment={len(sources.get("deployment",""))}, history={len(sources.get("incident_history",""))}')
    
    # Generate AI-powered recommendations
    recommendations = generate_ai_recommendations(sources, root_causes, service, alarm_name)
    
    # Generate summary
    summary = generate_summary(recommendations, sources)
    
    # Store to DynamoDB if we have incident_id
    if incident_id and recommendations:
        store_recommendations(incident_id, recommendations, summary)
    
    return {
        'statusCode': 200,
        'recommendations': recommendations,
        'summary': summary
    }


def generate_ai_recommendations(sources, root_causes, service, alarm_name):
    """Use Bedrock AI to generate smart, evidence-based recommendations."""
    
    # Build evidence sections - only include sources with actual data
    evidence_sections = []
    available_sources = []
    
    if sources.get('opensearch') and not is_no_data(sources['opensearch']):
        evidence_sections.append(f"LOG ANALYSIS (OpenSearch):\n{sources['opensearch']}")
        available_sources.append('AGENT:log_patterns')
    
    if sources.get('runbook') and not is_no_data(sources['runbook']):
        evidence_sections.append(f"RUNBOOK GUIDANCE:\n{sources['runbook']}")
        available_sources.append('AGENT:runbook')
    
    if sources.get('deployment') and not is_no_data(sources['deployment']):
        evidence_sections.append(f"DEPLOYMENT HISTORY:\n{sources['deployment']}")
        available_sources.append('AGENT:deployment_correlation')
    
    if sources.get('incident_history') and not is_no_data(sources['incident_history']):
        evidence_sections.append(f"PAST INCIDENTS:\n{sources['incident_history']}")
        available_sources.append('AGENT:past_incidents')
    
    # Get root cause description
    rc_desc = ''
    if root_causes:
        rc = root_causes[0] if root_causes else {}
        rc_desc = rc.get('description', '') if isinstance(rc, dict) else str(rc)
    
    # If no evidence at all, return basic recommendation from root cause
    if not evidence_sections:
        if rc_desc:
            return [{
                'category': 'manual_intervention',
                'description': f'Investigate the root cause: {rc_desc[:200]}. Check CloudWatch metrics, application logs, and recent changes.',
                'reasoning': 'Root cause analysis identified this issue. Manual investigation required.',
                'source': 'RCA',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 60,
                'confidence': 65
            }]
        return [{
            'category': 'manual_intervention',
            'description': f'Investigate the {service} service manually. Check CloudWatch metrics, application logs, and recent changes.',
            'reasoning': 'No specific evidence available from automated investigation.',
            'source': 'agent_advice',
            'effectiveness': 2,
            'risk': 'low',
            'estimated_ttr_minutes': 60,
            'confidence': 50
        }]
    
    # Build the prompt
    evidence_text = "\n\n".join(evidence_sections)
    
    prompt = f"""You are an expert SRE generating remediation recommendations for a production incident.

SERVICE: {service}
ALARM: {alarm_name or 'Unknown'}
ROOT CAUSE: {rc_desc or 'Under investigation'}

EVIDENCE FROM INVESTIGATION TOOLS:
{evidence_text}

AVAILABLE SOURCES FOR ATTRIBUTION: {', '.join(available_sources)}

STRICT RULES:
1. ONLY recommend actions supported by the evidence above
2. DO NOT invent or assume information not in the evidence
3. Each recommendation MUST cite its source from the available sources
4. If deployment/config change is found, prioritize rollback as first action
5. If runbook exists, include its specific steps
6. If past incidents found, reference the resolution approach
7. If logs show specific errors/alarms, address those patterns
8. Be specific - include version numbers, config names, error types from the evidence
9. Maximum 4 recommendations, prioritized by impact

Generate 1-4 remediation recommendations as a JSON array. Each recommendation must have:
- category: "rollback" | "scaling" | "configuration_change" | "manual_intervention"
- description: Clear, actionable step (2-3 sentences, specific to the evidence)
- reasoning: Why this action is recommended (reference specific evidence)
- source: One of [{', '.join(available_sources)}] - MUST match the evidence used
- effectiveness: 1-5 (5=highest impact)
- risk: "low" | "medium" | "high"
- estimated_ttr_minutes: Realistic time estimate
- confidence: 50-95 (based on evidence strength)

Return ONLY the JSON array, no other text."""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2000,
                'temperature': 0.3,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read().decode('utf-8'))
        content = result.get('content', [{}])[0].get('text', '[]')
        
        # Parse JSON from response
        recommendations = parse_json_response(content)
        
        # Validate and fix sources
        recommendations = validate_recommendations(recommendations, available_sources)
        
        print(f'AI generated {len(recommendations)} recommendations')
        return recommendations
        
    except Exception as e:
        print(f'Bedrock call failed: {e}')
        # Fallback to rule-based recommendations
        return generate_fallback_recommendations(sources, root_causes, service)


def parse_json_response(content):
    """Parse JSON from AI response, handling various formats."""
    content = content.strip()
    
    # Fix smart quotes and other unicode issues that break JSON parsing
    content = content.replace('\u201c', '"').replace('\u201d', '"')  # Smart double quotes
    content = content.replace('\u2018', "'").replace('\u2019', "'")  # Smart single quotes
    content = content.replace('\u2013', '-').replace('\u2014', '-')  # En/em dashes
    
    # Try to extract JSON array
    if '[' in content:
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            
            # First attempt - try parsing as-is
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
            
            # Fix unescaped quotes inside string values
            # This handles cases like: "description": "The "alarm" triggered"
            # by converting inner quotes to single quotes
            fixed = fix_unescaped_quotes(json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                print(f'JSON parse error after fix: {e}')
                # Try removing trailing commas
                fixed = re.sub(r',\s*]', ']', fixed)
                fixed = re.sub(r',\s*}', '}', fixed)
                try:
                    return json.loads(fixed)
                except:
                    pass
    
    # Try parsing as-is
    try:
        return json.loads(content)
    except:
        return []


def fix_unescaped_quotes(json_str):
    """Fix unescaped double quotes inside JSON string values."""
    result = []
    in_string = False
    escape_next = False
    i = 0
    
    while i < len(json_str):
        char = json_str[i]
        
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\\\':
            result.append(char)
            escape_next = True
            i += 1
            continue
        
        if char == '"':
            if not in_string:
                # Starting a string
                in_string = True
                result.append(char)
            else:
                # Check if this is the end of the string or an unescaped quote
                # Look ahead to see if this looks like end of string
                rest = json_str[i+1:].lstrip()
                if rest and rest[0] in ':,}]':
                    # This is the end of the string
                    in_string = False
                    result.append(char)
                elif rest and rest[0] == '"':
                    # Next non-space is another quote - this is end of string
                    in_string = False
                    result.append(char)
                else:
                    # This is an unescaped quote inside the string - replace with single quote
                    result.append("'")
        else:
            result.append(char)
        
        i += 1
    
    return ''.join(result)


def validate_recommendations(recommendations, available_sources):
    """Validate and fix recommendation sources."""
    valid_sources = set(available_sources + ['RCA', 'agent_advice'])
    validated = []
    
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        
        # Ensure required fields
        if not rec.get('description'):
            continue
        
        # Fix source if invalid
        source = rec.get('source', '')
        if source not in valid_sources:
            # Try to match partial source name
            for vs in available_sources:
                if vs.split(':')[-1].lower() in source.lower():
                    rec['source'] = vs
                    break
            else:
                rec['source'] = available_sources[0] if available_sources else 'RCA'
        
        # Ensure valid category
        valid_categories = ['rollback', 'scaling', 'configuration_change', 'manual_intervention']
        if rec.get('category') not in valid_categories:
            rec['category'] = 'manual_intervention'
        
        # Ensure numeric fields
        rec['effectiveness'] = min(5, max(1, int(rec.get('effectiveness', 3))))
        rec['confidence'] = min(95, max(50, int(rec.get('confidence', 70))))
        rec['estimated_ttr_minutes'] = max(5, int(rec.get('estimated_ttr_minutes', 30)))
        
        # Ensure risk
        if rec.get('risk') not in ['low', 'medium', 'high']:
            rec['risk'] = 'medium'
        
        validated.append(rec)
    
    return validated[:4]  # Max 4 recommendations


def generate_fallback_recommendations(sources, root_causes, service):
    """Generate rule-based recommendations as fallback."""
    recommendations = []
    
    # Deployment-based recommendation
    if sources.get('deployment') and not is_no_data(sources['deployment']):
        recommendations.append({
            'category': 'configuration_change',
            'description': f'Review and consider rolling back the recent deployment or configuration change to {service}. The deployment history shows changes that correlate with the incident timeline.',
            'reasoning': 'Deployment correlation found recent changes that may be causing the issue.',
            'source': 'AGENT:deployment_correlation',
            'effectiveness': 4,
            'risk': 'medium',
            'estimated_ttr_minutes': 30,
            'confidence': 75
        })
    
    # Log-based recommendation
    if sources.get('opensearch') and not is_no_data(sources['opensearch']):
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'Investigate the error patterns found in logs. Review CloudWatch metrics and correlate alarm triggers with the incident timeline.',
            'reasoning': 'Log analysis revealed alarm patterns that need investigation.',
            'source': 'AGENT:log_patterns',
            'effectiveness': 3,
            'risk': 'low',
            'estimated_ttr_minutes': 45,
            'confidence': 70
        })
    
    # Runbook-based recommendation
    if sources.get('runbook') and not is_no_data(sources['runbook']):
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'Follow the documented runbook procedures for this alarm type. The runbook provides specific troubleshooting steps.',
            'reasoning': 'A runbook with remediation guidance is available for this alarm.',
            'source': 'AGENT:runbook',
            'effectiveness': 3,
            'risk': 'low',
            'estimated_ttr_minutes': 30,
            'confidence': 80
        })
    
    # Past incidents recommendation
    if sources.get('incident_history') and not is_no_data(sources['incident_history']):
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'Apply the resolution approach from similar past incidents. Review historical incident data for context.',
            'reasoning': 'Similar incidents were found with documented resolutions.',
            'source': 'AGENT:past_incidents',
            'effectiveness': 4,
            'risk': 'medium',
            'estimated_ttr_minutes': 45,
            'confidence': 75
        })
    
    # Root cause based if nothing else
    if not recommendations and root_causes:
        rc = root_causes[0] if root_causes else {}
        rc_desc = rc.get('description', '') if isinstance(rc, dict) else str(rc)
        if rc_desc:
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'Investigate the identified root cause: {rc_desc[:150]}',
                'reasoning': 'Root cause analysis identified this as the likely cause.',
                'source': 'RCA',
                'effectiveness': 3,
                'risk': 'medium',
                'estimated_ttr_minutes': 60,
                'confidence': 65
            })
    
    return recommendations


def parse_investigation_sources(investigation):
    """Parse the agent investigation text and extract content for each source."""
    sources = {
        'opensearch': '',
        'runbook': '',
        'deployment': '',
        'incident_history': ''
    }
    
    if not investigation:
        return sources
    
    # Split by [Source: ...] tags and extract content
    # Pattern matches [Source: Something] or [Source: Something DB]
    sections = re.split(r'\[Source:\s*([^\]]+)\]', investigation, flags=re.IGNORECASE)
    
    # sections will be: [before_first_tag, tag1_name, tag1_content, tag2_name, tag2_content, ...]
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break
        
        tag_name = sections[i].strip().lower()
        content = sections[i + 1].strip()
        content = clean_text(content)
        
        if not content or len(content) < 10:
            continue
        
        # Map tag names to source keys
        if 'opensearch' in tag_name or 'log' in tag_name:
            sources['opensearch'] = content
        elif 'runbook' in tag_name:
            sources['runbook'] = content
        elif 'deployment' in tag_name or 'config' in tag_name:
            sources['deployment'] = content
        elif 'incident' in tag_name or 'history' in tag_name or 'past' in tag_name:
            sources['incident_history'] = content
    
    return sources


def is_no_data(content):
    """Check if the content indicates no data was found."""
    if not content:
        return True
    lower = content.lower().strip()
    
    # Check if it starts with "no" patterns
    no_data_patterns = [
        'no relevant data',
        'no data found',
        'no similar past incidents',
        'no past incidents',
        'no runbook found',
        'no deployment found',
        'no information available',
        'could not find',
        'unable to find',
        'no results',
        'no matching'
    ]
    
    # Check if content is primarily a "no data" message
    for pattern in no_data_patterns:
        if lower.startswith(pattern) or pattern in lower[:50]:
            return True
    
    return False


def clean_text(text):
    """Clean up text by removing redacted markers and extra whitespace."""
    if not text:
        return ''
    text = re.sub(r'<REDACTED>\s*/?', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def generate_summary(recommendations, sources):
    """Generate a clear, actionable summary of the remediation plan."""
    if not recommendations:
        return 'No specific remediation recommendations could be generated. Manual investigation required.'
    
    # Build evidence summary
    evidence_found = []
    if sources.get('deployment') and not is_no_data(sources['deployment']):
        evidence_found.append('deployment/config change')
    if sources.get('opensearch') and not is_no_data(sources['opensearch']):
        evidence_found.append('log patterns')
    if sources.get('runbook') and not is_no_data(sources['runbook']):
        evidence_found.append('runbook')
    if sources.get('incident_history') and not is_no_data(sources['incident_history']):
        evidence_found.append('past incidents')
    
    # Priority action
    top_rec = recommendations[0]
    top_action = top_rec.get('description', '').split('.')[0]
    
    # Build summary
    parts = []
    parts.append(f"PRIORITY: {top_action}.")
    
    if evidence_found:
        parts.append(f"Evidence: {', '.join(evidence_found)}.")
    
    # Action count
    if len(recommendations) > 1:
        parts.append(f"{len(recommendations)} recommended actions available.")
    
    # Confidence
    avg_conf = sum(r.get('confidence', 70) for r in recommendations) // len(recommendations)
    parts.append(f"Confidence: {avg_conf}%")
    
    return " ".join(parts)


def store_recommendations(incident_id, recommendations, summary=''):
    """Store recommendations to DynamoDB."""
    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        update_expr = 'SET recommendations_raw = :recs, workflow_step = :ws'
        values = {
            ':recs': json.dumps(recommendations, default=str),
            ':ws': 'remediation'
        }
        if summary:
            update_expr += ', remediation_summary = :rs'
            values[':rs'] = summary
        
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=values
        )
        print(f'Stored {len(recommendations)} recommendations for {incident_id}')
    except Exception as e:
        print(f'Store recommendations failed: {e}')
'''

# Create zip file
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', LAMBDA_CODE.strip())
zip_buffer.seek(0)

print("=" * 60)
print("Updating Remediation Lambda with AI-Powered Recommendations")
print("=" * 60)
print()
print("Features:")
print("  ✓ Uses Bedrock Claude to generate smart recommendations")
print("  ✓ Anti-hallucination: Only uses evidence from tools")
print("  ✓ Source attribution: Each recommendation cites its source")
print("  ✓ Validates sources against available evidence")
print("  ✓ Fallback to rule-based if AI fails")
print("  ✓ FIXED: Smart quotes and unicode handling in JSON parsing")
print()
print("Sources used:")
print("  - AGENT:log_patterns (OpenSearch logs)")
print("  - AGENT:runbook (Runbook DB)")
print("  - AGENT:deployment_correlation (Deployment History)")
print("  - AGENT:past_incidents (Incident History)")
print()

response = lambda_client.update_function_code(
    FunctionName='outageshield-remediation-recommend-dev',
    ZipFile=zip_buffer.read()
)
print(f"✓ Lambda updated! Last modified: {response['LastModified']}")
print()
print("Run 'python scripts/refresh-remediation.py' to regenerate recommendations.")
