"""
Update the remediation Lambda to use Bedrock AI for professional, evidence-based recommendations.
Follows SRE best practices and ITIL incident management framework.
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
from datetime import datetime

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
    
    # Parse investigation sources for evidence
    evidence = parse_investigation_evidence(agent_investigation)
    
    # Generate AI-powered recommendations using Bedrock
    recommendations = generate_bedrock_recommendations(
        service=service,
        alarm_name=alarm_name,
        root_causes=root_causes,
        evidence=evidence,
        agent_investigation=agent_investigation
    )
    
    # Generate summary
    summary = generate_summary(recommendations, evidence)
    
    # Store to DynamoDB if we have incident_id
    if incident_id and recommendations:
        store_recommendations(incident_id, recommendations, summary)
    
    return {
        'statusCode': 200,
        'recommendations': recommendations,
        'summary': summary
    }


def parse_investigation_evidence(investigation):
    """Extract structured evidence from agent investigation text."""
    evidence = {
        'log_entries': 0,
        'error_patterns': [],
        'deployment_count': 0,
        'config_changes': 0,
        'past_incidents': 0,
        'xray_requests': 0,
        'xray_errors': 0,
        'xray_faults': 0,
        'latency_p99': 0,
        'runbook_available': False,
        'runbook_steps': 0,
        'alarm_occurrences': 0,
        'compliance_issues': 0,
        'raw_sources': {}
    }
    
    if not investigation:
        return evidence
    
    inv_lower = investigation.lower()
    
    # Count log entries
    log_match = re.search(r'Found (\d+) log', investigation)
    if log_match:
        evidence['log_entries'] = int(log_match.group(1))
    
    # Count alarm occurrences (for pattern detection)
    evidence['alarm_occurrences'] = inv_lower.count('threshold crossed')
    
    # Extract deployment info
    deploy_match = re.search(r'Found (\d+) deployment', investigation)
    if deploy_match:
        evidence['deployment_count'] = int(deploy_match.group(1))
    
    config_match = re.search(r'(\d+) config change', investigation)
    if config_match:
        evidence['config_changes'] = int(config_match.group(1))
    
    # Extract X-Ray metrics
    requests_match = re.search(r'Total Requests?:\s*(\d+)', investigation)
    if requests_match:
        evidence['xray_requests'] = int(requests_match.group(1))
    
    errors_match = re.search(r'Errors?:\s*(\d+)', investigation)
    if errors_match:
        evidence['xray_errors'] = int(errors_match.group(1))
    
    faults_match = re.search(r'Faults?:\s*(\d+)', investigation)
    if faults_match:
        evidence['xray_faults'] = int(faults_match.group(1))
    
    latency_match = re.search(r'P99[^0-9]*(\d+)\s*ms', investigation, re.IGNORECASE)
    if latency_match:
        evidence['latency_p99'] = int(latency_match.group(1))
    
    # Check for runbook
    if 'runbook:' in inv_lower:
        evidence['runbook_available'] = True
        steps_match = re.search(r'(\d+)\s*steps', investigation)
        if steps_match:
            evidence['runbook_steps'] = int(steps_match.group(1))
    
    # Check for past incidents
    incident_match = re.search(r'Found (\d+) past incident', investigation)
    if incident_match:
        evidence['past_incidents'] = int(incident_match.group(1))
    
    # Check for compliance issues
    if 'non-compliant' in inv_lower or 'non_compliant' in inv_lower:
        evidence['compliance_issues'] = 1
    
    # Extract raw source sections
    sources = ['OpenSearch', 'Runbook', 'Deployment', 'X-Ray', 'Config', 'Incident History']
    for source in sources:
        pattern = rf'\[Source: {source}[^\]]*\](.*?)(?=\[Source:|$)'
        match = re.search(pattern, investigation, re.DOTALL | re.IGNORECASE)
        if match:
            evidence['raw_sources'][source.lower().replace(' ', '_')] = match.group(1).strip()[:500]
    
    return evidence


def generate_bedrock_recommendations(service, alarm_name, root_causes, evidence, agent_investigation):
    """Generate professional remediation recommendations using Bedrock AI, citing investigation sources."""
    
    # Build root cause summary
    rca_summary = ""
    if root_causes:
        for i, rc in enumerate(root_causes[:3]):
            rca_summary += f"{i+1}. {rc.get('description', 'Unknown')} (Confidence: {rc.get('confidence', 0)}%, Category: {rc.get('category', 'unknown')})\n"
    else:
        rca_summary = "No root causes identified"
    
    # Build source-specific evidence sections
    source_evidence = build_source_evidence(evidence, agent_investigation)
    
    prompt = f"""You are a Senior Site Reliability Engineer generating remediation recommendations for an incident.
Each recommendation MUST cite the specific investigation source it's based on.

INCIDENT DETAILS:
- Service: {service}
- Alarm: {alarm_name}

ROOT CAUSE ANALYSIS:
{rca_summary}

=== INVESTIGATION SOURCES ===

[SOURCE: OpenSearch Logs]
{source_evidence.get('opensearch', 'No log data available')}

[SOURCE: X-Ray Traces]
{source_evidence.get('xray', 'No trace data available')}

[SOURCE: Runbook DB]
{source_evidence.get('runbook', 'No runbook found')}

[SOURCE: Deployment History]
{source_evidence.get('deployment', 'No deployment data available')}

[SOURCE: AWS Config]
{source_evidence.get('config', 'No config data available')}

[SOURCE: Incident History]
{source_evidence.get('incident_history', 'No past incidents found')}

=== END SOURCES ===

GENERATE 5 RECOMMENDATIONS. Each recommendation MUST:
1. Be based on SPECIFIC evidence from one of the sources above
2. Include the source name in the "source" field
3. Quote specific data from that source in the "reasoning" field

CRITICAL RULES:
- If a source says "No data" or "0 requests", do NOT make recommendations based on it
- If OpenSearch shows repeated "Threshold Crossed" entries, this is a RECURRING issue
- If Runbook exists, include its steps in recommendations
- If X-Ray shows errors/faults, recommend trace analysis
- If no deployments found, do NOT recommend rollback
- If Config shows issues, recommend config remediation

Return a JSON array:
[
  {{
    "category": "immediate_mitigation|root_cause_remediation|configuration|monitoring|prevention",
    "title": "Short action title",
    "description": "What to do and why",
    "reasoning": "MUST quote specific evidence from the source, e.g., 'OpenSearch shows 5 occurrences of Threshold Crossed in 24 hours'",
    "source": "OpenSearch Logs|X-Ray Traces|Runbook DB|Deployment History|AWS Config|Incident History",
    "aws_command": "AWS CLI command or null",
    "estimated_ttr_minutes": number,
    "risk_level": "low|medium|high",
    "confidence": number 0-100,
    "verification": "How to verify the fix"
  }}
]

Return ONLY the JSON array."""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2500,
                'temperature': 0.1,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        body = json.loads(response['body'].read())
        text = body['content'][0]['text']
        
        # Parse JSON response
        recommendations = parse_json_array(text)
        
        # Validate and normalize recommendations
        validated = []
        for rec in recommendations:
            validated.append({
                'category': rec.get('category', 'manual_investigation'),
                'title': rec.get('title', 'Investigation Required'),
                'description': rec.get('description', ''),
                'reasoning': rec.get('reasoning', ''),
                'source': rec.get('source', 'Investigation'),
                'aws_command': rec.get('aws_command'),
                'estimated_ttr_minutes': int(rec.get('estimated_ttr_minutes', 30)),
                'risk': rec.get('risk_level', 'medium'),
                'confidence': int(rec.get('confidence', 50)),
                'verification': rec.get('verification', ''),
                'effectiveness': calculate_effectiveness(rec)
            })
        
        return validated if validated else get_fallback_recommendations(service, alarm_name, evidence)
        
    except Exception as e:
        print(f'Bedrock recommendation error: {e}')
        return get_fallback_recommendations(service, alarm_name, evidence)


def build_source_evidence(evidence, agent_investigation):
    """Extract and format evidence from each investigation source."""
    sources = {}
    
    # OpenSearch Logs
    opensearch_data = evidence['raw_sources'].get('opensearch', '')
    if opensearch_data or evidence['log_entries'] > 0:
        sources['opensearch'] = f"Found {evidence['log_entries']} log entries. Alarm triggered {evidence['alarm_occurrences']} times (Threshold Crossed events).\n{opensearch_data[:600]}"
    else:
        sources['opensearch'] = "No log entries found in OpenSearch."
    
    # X-Ray Traces
    if evidence['xray_requests'] > 0 or evidence['xray_errors'] > 0 or evidence['xray_faults'] > 0:
        sources['xray'] = f"Total Requests: {evidence['xray_requests']}, Errors: {evidence['xray_errors']}, Faults: {evidence['xray_faults']}, P99 Latency: {evidence['latency_p99']}ms"
        xray_raw = evidence['raw_sources'].get('x-ray', '')
        if xray_raw:
            sources['xray'] += f"\n{xray_raw[:400]}"
    else:
        sources['xray'] = "X-Ray tracing not enabled or no requests traced. Total Requests: 0"
    
    # Runbook
    if evidence['runbook_available']:
        runbook_raw = evidence['raw_sources'].get('runbook', '')
        sources['runbook'] = f"Runbook available with {evidence['runbook_steps']} steps.\n{runbook_raw[:500]}"
    else:
        sources['runbook'] = "No runbook found for this service."
    
    # Deployment History
    if evidence['deployment_count'] > 0:
        deploy_raw = evidence['raw_sources'].get('deployment', '')
        sources['deployment'] = f"Found {evidence['deployment_count']} recent deployments.\n{deploy_raw[:400]}"
    else:
        sources['deployment'] = "No recent deployments or config changes found in the last 24 hours."
    
    # AWS Config
    config_raw = evidence['raw_sources'].get('config', '')
    if evidence['compliance_issues'] > 0:
        sources['config'] = f"Found {evidence['compliance_issues']} compliance issues.\n{config_raw[:400]}"
    elif config_raw:
        sources['config'] = f"Config state reviewed.\n{config_raw[:400]}"
    else:
        sources['config'] = "No configuration issues detected."
    
    # Incident History
    if evidence['past_incidents'] > 0:
        history_raw = evidence['raw_sources'].get('incident_history', '')
        sources['incident_history'] = f"Found {evidence['past_incidents']} similar past incidents.\n{history_raw[:400]}"
    else:
        sources['incident_history'] = "No similar past incidents found for this service."
    
    return sources


def calculate_effectiveness(rec):
    """Calculate effectiveness score based on recommendation attributes."""
    score = 3  # Base score
    
    category_scores = {
        'immediate_mitigation': 5,
        'rollback': 5,
        'scaling': 4,
        'configuration': 4,
        'prevention': 4,
        'monitoring': 3,
        'manual_investigation': 2
    }
    
    score = category_scores.get(rec.get('category', ''), 3)
    
    # Boost if has specific command
    if rec.get('aws_command'):
        score += 1
    
    # Boost if high confidence
    if rec.get('confidence', 0) >= 80:
        score += 1
    
    return min(score, 5)


def get_fallback_recommendations(service, alarm_name, evidence):
    """Generate fallback recommendations when AI fails, citing investigation sources."""
    recommendations = []
    
    # OpenSearch Logs recommendation
    if evidence['log_entries'] > 0 or evidence['alarm_occurrences'] > 0:
        recommendations.append({
            'category': 'manual_investigation',
            'title': 'Analyze OpenSearch Logs',
            'description': f'Review the {evidence["log_entries"]} log entries found in OpenSearch to identify error patterns and root cause.',
            'reasoning': f'[Source: OpenSearch Logs] Found {evidence["log_entries"]} log entries with {evidence["alarm_occurrences"]} "Threshold Crossed" events indicating recurring alarm triggers.',
            'source': 'OpenSearch Logs',
            'aws_command': f'aws logs filter-log-events --log-group-name /aws/lambda/{service} --filter-pattern "ERROR" --start-time $(date -u -d "1 hour ago" +%s)000 --limit 50',
            'estimated_ttr_minutes': 15,
            'risk': 'low',
            'confidence': 70,
            'verification': 'Check if error patterns are identified and addressed',
            'effectiveness': 3
        })
    
    # Runbook recommendation
    if evidence['runbook_available']:
        recommendations.append({
            'category': 'manual_investigation',
            'title': 'Execute Service Runbook',
            'description': f'Follow the documented {evidence["runbook_steps"]}-step runbook for {service} troubleshooting.',
            'reasoning': f'[Source: Runbook DB] Runbook available with {evidence["runbook_steps"]} documented steps for this service type.',
            'source': 'Runbook DB',
            'aws_command': None,
            'estimated_ttr_minutes': 30,
            'risk': 'low',
            'confidence': 80,
            'verification': 'Complete all runbook steps and verify service health',
            'effectiveness': 4
        })
    
    # X-Ray recommendation
    if evidence['xray_requests'] > 0:
        recommendations.append({
            'category': 'manual_investigation',
            'title': 'Analyze X-Ray Traces',
            'description': f'Review X-Ray traces showing {evidence["xray_errors"]} errors and {evidence["xray_faults"]} faults.',
            'reasoning': f'[Source: X-Ray Traces] Captured {evidence["xray_requests"]} requests with {evidence["xray_errors"]} errors, {evidence["xray_faults"]} faults, P99 latency: {evidence["latency_p99"]}ms.',
            'source': 'X-Ray Traces',
            'aws_command': f'aws xray get-trace-summaries --start-time $(date -u -d "1 hour ago" +%s) --end-time $(date -u +%s) --filter-expression "service(id(name: \\"{service}\\")) AND (error = true OR fault = true)"',
            'estimated_ttr_minutes': 20,
            'risk': 'low',
            'confidence': 65,
            'verification': 'Identify root cause from trace segments',
            'effectiveness': 3
        })
    else:
        recommendations.append({
            'category': 'monitoring',
            'title': 'Enable X-Ray Tracing',
            'description': f'X-Ray tracing is not enabled for {service}. Enable it to get visibility into request flows and errors.',
            'reasoning': f'[Source: X-Ray Traces] Total Requests: 0. X-Ray tracing not enabled or no requests traced in the last hour.',
            'source': 'X-Ray Traces',
            'aws_command': f'aws lambda update-function-configuration --function-name {service} --tracing-config Mode=Active',
            'estimated_ttr_minutes': 5,
            'risk': 'low',
            'confidence': 90,
            'verification': 'Verify X-Ray traces appear in console after enabling',
            'effectiveness': 3
        })
    
    # Deployment recommendation
    if evidence['deployment_count'] > 0:
        recommendations.append({
            'category': 'root_cause_remediation',
            'title': 'Review Recent Deployments',
            'description': f'Investigate the {evidence["deployment_count"]} recent deployments that may have caused this issue.',
            'reasoning': f'[Source: Deployment History] Found {evidence["deployment_count"]} deployments in the last 24 hours that correlate with the incident timeline.',
            'source': 'Deployment History',
            'aws_command': f'aws lambda list-versions-by-function --function-name {service} --max-items 5',
            'estimated_ttr_minutes': 20,
            'risk': 'medium',
            'confidence': 70,
            'verification': 'Compare metrics before and after deployment',
            'effectiveness': 4
        })
    else:
        recommendations.append({
            'category': 'root_cause_remediation',
            'title': 'Investigate Non-Deployment Causes',
            'description': 'No recent deployments found. Focus on traffic patterns, dependencies, or configuration drift.',
            'reasoning': '[Source: Deployment History] No recent deployments or config changes found in the last 24 hours. Issue is likely not deployment-related.',
            'source': 'Deployment History',
            'aws_command': None,
            'estimated_ttr_minutes': 30,
            'risk': 'low',
            'confidence': 60,
            'verification': 'Rule out deployment as root cause',
            'effectiveness': 2
        })
    
    # Config recommendation
    if evidence['compliance_issues'] > 0:
        recommendations.append({
            'category': 'configuration',
            'title': 'Fix Config Compliance Issues',
            'description': f'Address the {evidence["compliance_issues"]} compliance issues detected by AWS Config.',
            'reasoning': f'[Source: AWS Config] Found {evidence["compliance_issues"]} non-compliant resources that may be contributing to the incident.',
            'source': 'AWS Config',
            'aws_command': 'aws configservice get-compliance-details-by-config-rule --config-rule-name lambda-function-public-access-prohibited --compliance-types NON_COMPLIANT',
            'estimated_ttr_minutes': 45,
            'risk': 'medium',
            'confidence': 75,
            'verification': 'Re-run compliance check after remediation',
            'effectiveness': 4
        })
    
    # Incident History recommendation
    if evidence['past_incidents'] > 0:
        recommendations.append({
            'category': 'prevention',
            'title': 'Review Past Incident Patterns',
            'description': f'This service has {evidence["past_incidents"]} similar past incidents. Review them for recurring patterns.',
            'reasoning': f'[Source: Incident History] Found {evidence["past_incidents"]} past incidents for this service, indicating a recurring issue that needs permanent fix.',
            'source': 'Incident History',
            'aws_command': None,
            'estimated_ttr_minutes': 30,
            'risk': 'low',
            'confidence': 80,
            'verification': 'Implement permanent fix to prevent recurrence',
            'effectiveness': 4
        })
    
    return recommendations


def parse_json_array(text):
    """Parse JSON array from AI response."""
    text = text.strip()
    
    # Find JSON array
    start = text.find('[')
    end = text.rfind(']') + 1
    
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix common issues
            json_str = json_str.replace('\n', ' ')
            json_str = re.sub(r',\s*]', ']', json_str)
            json_str = re.sub(r',\s*}', '}', json_str)
            try:
                return json.loads(json_str)
            except:
                pass
    
    return []


def generate_summary(recommendations, evidence):
    """Generate a summary of recommendations."""
    categories = {}
    for rec in recommendations:
        cat = rec.get('category', 'other')
        categories[cat] = categories.get(cat, 0) + 1
    
    return {
        'total_recommendations': len(recommendations),
        'by_category': categories,
        'evidence_summary': {
            'logs_analyzed': evidence['log_entries'],
            'alarm_occurrences': evidence['alarm_occurrences'],
            'deployments_found': evidence['deployment_count'],
            'xray_traces': evidence['xray_requests']
        },
        'generated_at': datetime.utcnow().isoformat() + 'Z'
    }


def store_recommendations(incident_id, recommendations, summary):
    """Store recommendations to DynamoDB."""
    table = dynamodb.Table(INCIDENTS_TABLE)
    try:
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET recommendations_raw = :r, remediation_summary = :s, workflow_step = :ws',
            ExpressionAttributeValues={
                ':r': json.dumps(recommendations),
                ':s': json.dumps(summary),
                ':ws': 'remediation'
            }
        )
        print(f'Stored {len(recommendations)} recommendations for {incident_id}')
    except Exception as e:
        print(f'Store recommendations failed: {e}')
'''

# Create deployment package
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', LAMBDA_CODE)
zip_buffer.seek(0)

print('=' * 60)
print('Updating Remediation Lambda with AI-Powered Recommendations')
print('=' * 60)
print()
print('Features:')
print('  ✓ Uses Bedrock AI for evidence-based recommendations')
print('  ✓ Follows SRE best practices and ITIL framework')
print('  ✓ Extracts structured evidence from investigation')
print('  ✓ Generates specific AWS CLI commands')
print('  ✓ Includes verification steps for each recommendation')
print('  ✓ Calculates confidence based on evidence strength')
print()

response = lambda_client.update_function_code(
    FunctionName='outageshield-remediation-recommend-dev',
    ZipFile=zip_buffer.read()
)

print(f'✓ Lambda updated! Last modified: {response["LastModified"]}')
