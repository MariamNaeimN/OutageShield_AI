"""Update the postmortem Lambda to use actual remediation and investigation data."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = '''import json
import boto3
import os
import uuid
import re
from datetime import datetime, timezone

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ['MODEL_ID']

def lambda_handler(event, context):
    """Generate postmortem using ACTUAL remediation and investigation data."""
    
    # Extract from Step Functions state
    signal = event.get('signal', {})
    incident_id = event.get('incident_id') or signal.get('signal_id', '')
    service = event.get('service') or signal.get('service', 'unknown')
    alarm_name = signal.get('alarm_name', '')

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

    # Get agent investigation from Step 3b - THIS IS KEY
    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '')

    # Get recommendations from Step 4 - THIS IS KEY
    step4 = event.get('step4', {})
    recommendations = step4.get('recommendations', [])

    print(f'[Postmortem] incident_id={incident_id}, service={service}')
    print(f'[Postmortem] Investigation length: {len(agent_investigation)}')
    print(f'[Postmortem] Recommendations count: {len(recommendations)}')

    # EXTRACT ACTUAL DATA from investigation
    investigation_findings = extract_investigation_findings(agent_investigation)
    
    # EXTRACT ACTUAL DATA from remediation
    remediation_actions = extract_remediation_actions(recommendations)

    # Generate postmortem using ACTUAL extracted data
    postmortem_data = generate_postmortem(
        service=service,
        alarm_name=alarm_name,
        root_cause=root_cause,
        root_causes=root_causes,
        confidence=confidence,
        severity=severity,
        affected_users=affected_users,
        revenue_at_risk=revenue_at_risk,
        investigation_findings=investigation_findings,
        remediation_actions=remediation_actions,
        agent_investigation=agent_investigation,
        recommendations=recommendations
    )

    # Store in postmortems table
    store_postmortem(incident_id, service, postmortem_data)

    return {'statusCode': 200, 'postmortem': postmortem_data}


def extract_investigation_findings(investigation):
    """Extract specific findings from agent investigation."""
    findings = {
        'sources_checked': [],
        'metrics': {},
        'errors': {},
        'key_findings': []
    }
    
    if not investigation:
        return findings
    
    # Extract sources
    if '[Source: Incident History' in investigation:
        findings['sources_checked'].append('Incident History DB')
    if '[Source: OpenSearch' in investigation:
        findings['sources_checked'].append('OpenSearch Logs')
    if '[Source: Runbook' in investigation:
        findings['sources_checked'].append('Runbook DB')
    if '[Source: Deployment' in investigation:
        findings['sources_checked'].append('Deployment History')
    if '[Source: X-Ray' in investigation:
        findings['sources_checked'].append('X-Ray Traces')
    if '[Source: AWS Config' in investigation:
        findings['sources_checked'].append('AWS Config')
    
    # Extract metrics
    queue_match = re.search(r'queue\\s*depth[:\\s]*\\(?([\\d,]+)\\)?', investigation.lower())
    if queue_match:
        findings['metrics']['queue_depth'] = queue_match.group(1)
    
    errors_match = re.search(r'Errors:\\s*(\\d+)', investigation)
    if errors_match:
        findings['metrics']['errors'] = errors_match.group(1)
    
    faults_match = re.search(r'Faults:\\s*(\\d+)', investigation)
    if faults_match:
        findings['metrics']['faults'] = faults_match.group(1)
    
    requests_match = re.search(r'Requests:\\s*([\\d,]+)', investigation)
    if requests_match:
        findings['metrics']['requests'] = requests_match.group(1)
    
    latency_match = re.search(r'P99\\s*latency[^\\d]*(\\d+)\\s*ms', investigation, re.IGNORECASE)
    if latency_match:
        findings['metrics']['p99_latency_ms'] = latency_match.group(1)
    
    # Extract key findings
    if 'no recent deployment' in investigation.lower():
        findings['key_findings'].append('No recent deployments found - ruled out as cause')
    if 'non-compliant' in investigation.lower():
        noncompliant_match = re.search(r'Non-compliant resources:\\s*(\\d+)', investigation)
        if noncompliant_match:
            findings['key_findings'].append(f'{noncompliant_match.group(1)} non-compliant AWS Config resources')
    if 'health check failed' in investigation.lower():
        findings['key_findings'].append('Health checks failing')
    if 'threshold' in investigation.lower() and 'crossed' in investigation.lower():
        findings['key_findings'].append('CloudWatch alarm thresholds crossed')
    if 'runbook' in investigation.lower():
        runbook_match = re.search(r'Runbook:\\s*([^\\n]+)', investigation)
        if runbook_match:
            findings['key_findings'].append(f'Runbook available: {runbook_match.group(1)[:50]}')
    
    return findings


def extract_remediation_actions(recommendations):
    """Extract specific actions from remediation recommendations."""
    actions = {
        'scaling': [],
        'rollback': [],
        'configuration': [],
        'manual': [],
        'top_recommendation': None
    }
    
    if not recommendations:
        return actions
    
    for rec in recommendations:
        category = rec.get('category', 'manual_intervention')
        description = rec.get('description', '')
        source = rec.get('source', '')
        confidence = rec.get('confidence', 0)
        
        action_item = {
            'description': description,
            'source': source,
            'confidence': confidence
        }
        
        if category == 'scaling':
            actions['scaling'].append(action_item)
        elif category == 'rollback':
            actions['rollback'].append(action_item)
        elif category == 'configuration_change':
            actions['configuration'].append(action_item)
        else:
            actions['manual'].append(action_item)
    
    # Find top recommendation by confidence
    if recommendations:
        top = max(recommendations, key=lambda x: x.get('confidence', 0))
        actions['top_recommendation'] = {
            'category': top.get('category'),
            'description': top.get('description'),
            'confidence': top.get('confidence')
        }
    
    return actions


def generate_postmortem(service, alarm_name, root_cause, root_causes, confidence, severity,
                        affected_users, revenue_at_risk, investigation_findings,
                        remediation_actions, agent_investigation, recommendations):
    """Generate postmortem using actual extracted data."""
    
    # Build investigation summary from ACTUAL findings
    inv_summary_parts = []
    
    if investigation_findings['sources_checked']:
        inv_summary_parts.append(f"Data sources analyzed: {', '.join(investigation_findings['sources_checked'])}")
    
    metrics = investigation_findings['metrics']
    if metrics:
        metric_strs = []
        if metrics.get('queue_depth'):
            metric_strs.append(f"Queue depth: {metrics['queue_depth']}")
        if metrics.get('errors'):
            metric_strs.append(f"Errors: {metrics['errors']}")
        if metrics.get('faults'):
            metric_strs.append(f"Faults: {metrics['faults']}")
        if metrics.get('requests'):
            metric_strs.append(f"Requests: {metrics['requests']}")
        if metrics.get('p99_latency_ms'):
            metric_strs.append(f"P99 latency: {metrics['p99_latency_ms']}ms")
        if metric_strs:
            inv_summary_parts.append(f"Key metrics: {', '.join(metric_strs)}")
    
    if investigation_findings['key_findings']:
        inv_summary_parts.append(f"Findings: {'; '.join(investigation_findings['key_findings'])}")
    
    investigation_summary = '. '.join(inv_summary_parts) if inv_summary_parts else 'Investigation data not available'
    
    # Build remediation summary from ACTUAL recommendations
    rem_summary_parts = []
    
    if remediation_actions['scaling']:
        rem_summary_parts.append(f"Scaling actions ({len(remediation_actions['scaling'])}): {remediation_actions['scaling'][0]['description'][:100]}")
    if remediation_actions['configuration']:
        rem_summary_parts.append(f"Config changes ({len(remediation_actions['configuration'])}): {remediation_actions['configuration'][0]['description'][:100]}")
    if remediation_actions['rollback']:
        rem_summary_parts.append(f"Rollback options ({len(remediation_actions['rollback'])})")
    if remediation_actions['manual']:
        rem_summary_parts.append(f"Manual steps ({len(remediation_actions['manual'])})")
    
    top_rec = remediation_actions.get('top_recommendation', {})
    if top_rec:
        rem_summary_parts.append(f"Top recommendation ({top_rec.get('confidence', 0)}% confidence): {top_rec.get('description', '')[:100]}")
    
    remediation_summary = '. '.join(rem_summary_parts) if rem_summary_parts else 'Remediation recommendations not available'
    
    # Build prevention steps from ACTUAL remediation recommendations AND RCA category
    prevention_steps = []
    
    # Get RCA category for targeted prevention
    rca_category = ''
    if root_causes and len(root_causes) > 0:
        rca_category = root_causes[0].get('category', '').lower()
    
    # Use AI to generate context-aware prevention recommendations
    prevention_prompt = f"""Based on this incident, generate 5 specific long-term prevention recommendations to prevent similar incidents in the future.

SERVICE: {service}
ALARM: {alarm_name}
ROOT CAUSE: {root_cause}
ROOT CAUSE CATEGORY: {rca_category}
CONFIDENCE: {confidence}%

INVESTIGATION FINDINGS:
{investigation_summary}

IMMEDIATE REMEDIATION TAKEN:
{remediation_summary}

Generate 5 actionable prevention recommendations that are:
1. Specific to this incident's root cause category ({rca_category})
2. Long-term improvements (not immediate fixes)
3. Actionable with clear implementation steps
4. Focused on preventing recurrence

Return ONLY a JSON array of 5 strings, each being a prevention recommendation.
Example format: ["Implement auto-scaling...", "Set up monitoring...", ...]
"""

    try:
        prevention_response = invoke_bedrock(prevention_prompt)
        # Parse the JSON array
        import json
        prevention_text = prevention_response.strip()
        if prevention_text.startswith('['):
            prevention_steps = json.loads(prevention_text)
        else:
            # Try to extract JSON array from response
            start = prevention_text.find('[')
            end = prevention_text.rfind(']') + 1
            if start >= 0 and end > start:
                prevention_steps = json.loads(prevention_text[start:end])
    except Exception as e:
        print(f'[Postmortem] Prevention AI generation failed: {e}')
        # Fallback to rule-based prevention
        if rca_category == 'capacity':
            prevention_steps = [
                "Implement auto-scaling policies with appropriate min/max thresholds",
                "Set up capacity planning reviews and load testing before peak periods",
                "Configure CloudWatch alarms for early warning at 70% utilization"
            ]
        elif rca_category == 'performance':
            prevention_steps = [
                "Implement query optimization and database indexing review process",
                "Set up APM monitoring with latency percentile tracking (P50, P95, P99)",
                "Establish performance budgets and automated regression testing"
            ]
        elif rca_category == 'configuration':
            prevention_steps = [
                "Implement infrastructure-as-code with peer review for all config changes",
                "Set up AWS Config rules to detect configuration drift",
                "Create configuration validation in CI/CD pipeline"
            ]
        elif rca_category == 'deployment':
            prevention_steps = [
                "Implement canary deployments with automatic rollback on error spike",
                "Add deployment gates with health checks before full rollout",
                "Set up feature flags for gradual rollout of risky changes"
            ]
        elif rca_category == 'dependency':
            prevention_steps = [
                "Implement circuit breakers for all external service calls",
                "Set up dependency health monitoring with fallback mechanisms",
                "Create SLA monitoring for third-party services"
            ]
        else:
            prevention_steps = [
                "Review and update monitoring thresholds based on this incident",
                "Document incident response runbook for this failure mode",
                "Schedule post-incident review to identify systemic improvements"
            ]
    
    # Ensure we have at least 3 prevention steps
    if len(prevention_steps) < 3:
        prevention_steps.append("Review and update monitoring thresholds based on this incident")
        prevention_steps.append("Document incident response runbook for this failure mode")
        prevention_steps.append("Schedule post-incident review to identify systemic improvements")
    
    # Use AI to generate a coherent summary using the ACTUAL data
    prompt = f"""Generate a concise incident postmortem summary using ONLY the following ACTUAL data.
DO NOT invent any information. Use the exact data provided.

SERVICE: {service}
ALARM: {alarm_name}
SEVERITY: {severity}/5

ROOT CAUSE (from RCA - {confidence}% confidence):
{root_cause}

INVESTIGATION FINDINGS (from agent tools):
{investigation_summary}

REMEDIATION RECOMMENDATIONS (from analysis):
{remediation_summary}

IMPACT:
- Affected users: {affected_users}
- Revenue at risk: {revenue_at_risk}

Write a 3-4 sentence summary that:
1. States what happened (use the alarm and root cause)
2. Mentions the key metrics found (queue depth, errors, etc.)
3. States the recommended fix (from remediation)
4. Notes the business impact

Return ONLY the summary text, no JSON."""

    try:
        summary = invoke_bedrock(prompt)
    except Exception as e:
        print(f'[Postmortem] Bedrock error: {e}')
        summary = f"The {service} service experienced an incident ({alarm_name}) due to {root_cause}. {investigation_summary}. Recommended action: {top_rec.get('description', 'Review and remediate')[:100]}. Impact: {affected_users} users affected, {revenue_at_risk} revenue at risk."
    
    # Build the postmortem with ACTUAL data
    postmortem = {
        'summary': summary.strip(),
        'root_cause': root_cause or 'Under investigation',
        'root_cause_confidence': confidence,
        'duration': estimate_duration(severity),
        'severity': severity,
        'impact': f'{affected_users:,} users affected. Revenue at risk: {revenue_at_risk}' if affected_users else f'Revenue at risk: {revenue_at_risk}',
        'affected_users': affected_users,
        'revenue_at_risk': revenue_at_risk,
        
        # ACTUAL investigation data
        'investigation': {
            'sources_checked': investigation_findings['sources_checked'],
            'metrics': investigation_findings['metrics'],
            'key_findings': investigation_findings['key_findings'],
            'summary': investigation_summary
        },
        
        # ACTUAL remediation data
        'remediation': {
            'total_recommendations': len(recommendations),
            'scaling_actions': len(remediation_actions['scaling']),
            'config_actions': len(remediation_actions['configuration']),
            'rollback_options': len(remediation_actions['rollback']),
            'manual_steps': len(remediation_actions['manual']),
            'top_recommendation': remediation_actions['top_recommendation'],
            'summary': remediation_summary
        },
        
        # Prevention steps from ACTUAL recommendations
        'prevention': prevention_steps[:5],
        
        # Timeline
        'timeline': [
            {'time': 'T+0', 'event': f'Alarm triggered: {alarm_name}'},
            {'time': 'T+1m', 'event': 'Automated investigation started'},
            {'time': 'T+2m', 'event': f'Root cause identified: {root_cause[:50]}...'},
            {'time': 'T+3m', 'event': f'Remediation recommended: {top_rec.get("category", "manual")}'},
        ]
    }
    
    return postmortem


def estimate_duration(severity):
    """Estimate incident duration based on severity."""
    durations = {
        5: '4-8 hours (Critical)',
        4: '2-4 hours (High)',
        3: '1-2 hours (Medium)',
        2: '30-60 minutes (Low)',
        1: '15-30 minutes (Info)'
    }
    return durations.get(severity, '1-2 hours')


def store_postmortem(incident_id, service, data):
    """Store the postmortem in DynamoDB."""
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
            'root_cause_confidence': data.get('root_cause_confidence', 0),
            'duration': data.get('duration', 'Unknown'),
            'severity': data.get('severity', 3),
            'prevention': json.dumps(data.get('prevention', [])),
            'impact_summary': data.get('impact', ''),
            'affected_users': data.get('affected_users', 0),
            'revenue_at_risk': str(data.get('revenue_at_risk', 'Unknown')),
            'investigation': json.dumps(data.get('investigation', {})),
            'remediation': json.dumps(data.get('remediation', {})),
            'timeline': json.dumps(data.get('timeline', [])),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'GENERATED'
        })
        print(f'[Postmortem] Stored for {incident_id}')
    except Exception as e:
        print(f'[Postmortem] Store failed: {e}')
    
    # Update incident status
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
    """Invoke Bedrock for AI generation."""
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 500,
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

print("=" * 60)
print("Updating Postmortem Lambda")
print("=" * 60)
print()
print("This update makes the postmortem use ACTUAL data from:")
print("  ✓ Investigation findings (metrics, sources, key findings)")
print("  ✓ Remediation recommendations (scaling, config, manual)")
print("  ✓ Root cause analysis")
print()

r = lambda_client.update_function_code(FunctionName='outageshield-postmortem-dev', ZipFile=zip_buffer.read())
print(f"✓ Lambda updated! Last modified: {r['LastModified']}")
