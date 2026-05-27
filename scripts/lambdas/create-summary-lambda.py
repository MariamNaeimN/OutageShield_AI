"""
Create a new Lambda that summarizes the investigation and remediation findings
to suggest the most effective way to remediate the issue.
"""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')
iam_client = boto3.client('iam', region_name='us-east-1')

LAMBDA_NAME = 'outageshield-remediation-summary-dev'

LAMBDA_CODE = r'''
import json
import boto3
import os
from datetime import datetime

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')
AI_REASONING_TABLE = os.environ.get('AI_REASONING_TABLE', 'outageshield-ai-reasoning-dev')


def fetch_recommendations_from_db(incident_id):
    """Fetch recommendations from DynamoDB if not in event."""
    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item', {})
        raw = item.get('recommendations_raw', '')
        if raw:
            if isinstance(raw, str):
                return json.loads(raw)
            return raw
    except Exception as e:
        print(f'[Summary] Failed to fetch recommendations from DB: {e}')
    return []


def lambda_handler(event, context):
    """
    Summarize investigation and remediation findings to suggest the most effective remediation.
    This runs AFTER the remediation recommendations are generated.
    """
    print(f'[Summary] Event keys: {list(event.keys())}')
    print(f'[Summary] Full event: {json.dumps(event, default=str)[:2000]}')
    
    # Extract data from the workflow
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    service = signal.get('service', 'unknown')
    alarm_name = signal.get('alarm_name', '')
    
    # Get correlation context - stored in step1
    step1 = event.get('step1', {})
    correlation = event.get('correlation_result', step1)
    incident_context = correlation.get('incident_context', {})
    
    # Get scoring - stored in step2
    step2 = event.get('step2', {})
    scoring = event.get('scoring_result', step2)
    severity = scoring.get('severity_score', 3)
    business_impact = scoring.get('business_impact_score', 5)
    
    # Get root cause analysis - stored in step3
    step3 = event.get('step3', {})
    rca = event.get('rca_result', step3)
    root_causes = rca.get('root_causes', [])
    
    # Get agent investigation - stored in step3b
    step3b = event.get('step3b', {})
    agent_investigation = step3b.get('investigation', '')
    
    # Get remediation recommendations - stored in step4
    step4 = event.get('step4', {})
    remediation = event.get('remediation_result', step4)
    recommendations = remediation.get('recommendations', [])
    
    # If recommendations still empty, try to fetch from DynamoDB
    if not recommendations and incident_id:
        print(f'[Summary] No recommendations in event, fetching from DynamoDB')
        recommendations = fetch_recommendations_from_db(incident_id)
    
    print(f'[Summary] incident_id={incident_id}, service={service}, recommendations={len(recommendations)}')
    print(f'[Summary] Root causes: {len(root_causes)}, Agent investigation length: {len(agent_investigation)}')
    
    # Generate the summary
    summary = generate_summary(
        incident_id=incident_id,
        service=service,
        alarm_name=alarm_name,
        severity=severity,
        business_impact=business_impact,
        root_causes=root_causes,
        agent_investigation=agent_investigation,
        recommendations=recommendations,
        incident_context=incident_context
    )
    
    # Store summary to DynamoDB
    if incident_id:
        store_summary(incident_id, summary)
    
    return {
        'statusCode': 200,
        'summary': summary
    }


def generate_summary(incident_id, service, alarm_name, severity, business_impact, 
                     root_causes, agent_investigation, recommendations, incident_context):
    """Generate a comprehensive summary with the most effective remediation suggestion."""
    
    # Analyze recommendations to find the best one
    best_recommendation = find_best_recommendation(recommendations)
    
    # Categorize recommendations
    scaling_recs = [r for r in recommendations if r.get('category') == 'scaling']
    rollback_recs = [r for r in recommendations if r.get('category') == 'rollback']
    config_recs = [r for r in recommendations if r.get('category') == 'configuration_change']
    manual_recs = [r for r in recommendations if r.get('category') == 'manual_intervention']
    
    # Build investigation summary
    investigation_summary = summarize_investigation(agent_investigation)
    
    # Build root cause summary
    root_cause_summary = ""
    if root_causes:
        primary = root_causes[0] if root_causes else {}
        root_cause_summary = primary.get('description', 'Unknown root cause')
        confidence = primary.get('confidence', 0)
        root_cause_summary = f"{root_cause_summary} (Confidence: {confidence}%)"
    
    # Determine the recommended action type
    if best_recommendation:
        action_type = best_recommendation.get('category', 'manual_intervention')
        action_desc = best_recommendation.get('description', '')
        action_confidence = best_recommendation.get('confidence', 0)
        action_ttr = best_recommendation.get('estimated_ttr_minutes', 30)
        action_risk = best_recommendation.get('risk', 'medium')
    else:
        action_type = 'manual_intervention'
        action_desc = 'Follow standard troubleshooting procedures'
        action_confidence = 50
        action_ttr = 60
        action_risk = 'low'
    
    # Generate AI-powered summary using Bedrock
    ai_summary = generate_ai_summary(
        service=service,
        alarm_name=alarm_name,
        severity=severity,
        root_cause_summary=root_cause_summary,
        investigation_summary=investigation_summary,
        best_recommendation=best_recommendation,
        scaling_count=len(scaling_recs),
        rollback_count=len(rollback_recs),
        config_count=len(config_recs)
    )
    
    summary = {
        'incident_id': incident_id,
        'service': service,
        'alarm_name': alarm_name,
        'severity': severity,
        'business_impact': business_impact,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        
        # Investigation Summary
        'investigation_summary': investigation_summary,
        'root_cause': root_cause_summary,
        'data_sources_analyzed': count_data_sources(agent_investigation),
        
        # Remediation Summary
        'total_recommendations': len(recommendations),
        'recommendation_breakdown': {
            'scaling': len(scaling_recs),
            'rollback': len(rollback_recs),
            'configuration_change': len(config_recs),
            'manual_intervention': len(manual_recs)
        },
        
        # Best Recommendation
        'recommended_action': {
            'type': action_type,
            'description': action_desc,
            'confidence': action_confidence,
            'estimated_ttr_minutes': action_ttr,
            'risk': action_risk,
            'reasoning': best_recommendation.get('reasoning', '') if best_recommendation else ''
        },
        
        # AI-Generated Summary
        'ai_summary': ai_summary,
        
        # Quick Actions - generate based on ALL relevant categories, not just one
        'quick_actions': generate_smart_quick_actions(
            recommendations=recommendations,
            service=service,
            alarm_name=alarm_name,
            root_cause_summary=root_cause_summary,
            agent_investigation=agent_investigation
        )
    }
    
    return summary


def find_best_recommendation(recommendations):
    """Find the most effective recommendation based on confidence and effectiveness."""
    if not recommendations:
        return None
    
    # Score each recommendation
    scored = []
    for rec in recommendations:
        # Prioritize automated actions over manual - but boost scaling for capacity issues
        category_score = {
            'rollback': 10,
            'scaling': 9,  # Increased from 8 - scaling is often the fastest fix
            'configuration_change': 6,
            'manual_intervention': 2
        }.get(rec.get('category', 'manual_intervention'), 2)
        
        confidence = rec.get('confidence', 50)
        effectiveness = rec.get('effectiveness', 3)
        
        # Calculate total score
        total_score = (confidence * 0.4) + (effectiveness * 10) + category_score
        scored.append((total_score, rec))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    return scored[0][1] if scored else None


def summarize_investigation(investigation):
    """Extract key technical findings from the investigation text for developers."""
    if not investigation:
        return "No investigation data available."
    
    findings = []
    details = []
    
    # Extract specific metrics and values
    import re
    
    # Look for error rates
    error_match = re.search(r'(\d+(?:\.\d+)?)\s*%?\s*(?:error|5xx|fault)', investigation.lower())
    if error_match:
        details.append(f"Error rate: {error_match.group(1)}%")
    
    # Look for latency values
    latency_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ms|milliseconds?|seconds?)\s*(?:latency|response)', investigation.lower())
    if latency_match:
        details.append(f"Latency: {latency_match.group(1)}ms")
    
    # Look for queue depth
    queue_match = re.search(r'queue\s*(?:depth|size|backlog)[:\s]*(\d+)', investigation.lower())
    if queue_match:
        details.append(f"Queue depth: {queue_match.group(1)}")
    
    # Look for request counts
    request_match = re.search(r'requests?[:\s]*(\d+)', investigation.lower())
    if request_match:
        details.append(f"Requests: {request_match.group(1)}")
    
    # Check for key patterns
    if 'deployment' in investigation.lower() or 'deploy' in investigation.lower():
        if 'no recent' in investigation.lower() or 'no deployment' in investigation.lower():
            findings.append("No recent deployments")
        else:
            findings.append("Recent deployment detected")
    
    if 'latency' in investigation.lower() or 'slow' in investigation.lower():
        findings.append("Latency anomaly")
    
    if 'error' in investigation.lower() or '5xx' in investigation.lower() or '4xx' in investigation.lower():
        findings.append("Error spike")
    
    if 'threshold' in investigation.lower() or 'exceeded' in investigation.lower():
        findings.append("Threshold breach")
    
    if 'runbook' in investigation.lower():
        findings.append("Runbook available")
    
    if 'x-ray' in investigation.lower() or 'trace' in investigation.lower():
        findings.append("Traces analyzed")
    
    if 'config' in investigation.lower():
        if 'non-compliant' in investigation.lower():
            findings.append("Config compliance issues")
        else:
            findings.append("Config checked")
    
    if 'memory' in investigation.lower() or 'cpu' in investigation.lower():
        findings.append("Resource metrics reviewed")
    
    # Combine findings
    result_parts = []
    if details:
        result_parts.append("Metrics: " + ", ".join(details))
    if findings:
        result_parts.append("Findings: " + ", ".join(findings))
    
    if result_parts:
        return " | ".join(result_parts)
    return "Investigation completed - review logs for details"


def count_data_sources(investigation):
    """Count how many data sources were analyzed."""
    sources = 0
    if 'opensearch' in investigation.lower() or 'log' in investigation.lower():
        sources += 1
    if 'deployment' in investigation.lower():
        sources += 1
    if 'runbook' in investigation.lower():
        sources += 1
    if 'incident' in investigation.lower() or 'history' in investigation.lower():
        sources += 1
    if 'x-ray' in investigation.lower() or 'trace' in investigation.lower():
        sources += 1
    if 'config' in investigation.lower() or 'drift' in investigation.lower():
        sources += 1
    return max(sources, 1)


def generate_ai_summary(service, alarm_name, severity, root_cause_summary, 
                        investigation_summary, best_recommendation, 
                        scaling_count, rollback_count, config_count):
    """Generate a developer-focused AI summary using Bedrock."""
    
    action_type = best_recommendation.get('category', 'manual') if best_recommendation else 'manual'
    action_desc = best_recommendation.get('description', '') if best_recommendation else ''
    action_reasoning = best_recommendation.get('reasoning', '') if best_recommendation else ''
    action_source = best_recommendation.get('source', '') if best_recommendation else ''
    
    prompt = f"""You are a senior SRE engineer writing a technical incident summary for developers. Be specific and actionable.

INCIDENT CONTEXT:
- Service: {service}
- Alarm: {alarm_name}
- Severity: {severity}/5
- Root Cause: {root_cause_summary}
- Investigation Findings: {investigation_summary}
- Evidence: {action_reasoning[:500] if action_reasoning else 'No specific evidence'}

RECOMMENDED ACTION:
- Type: {action_type}
- Description: {action_desc}
- Source: {action_source}

AVAILABLE OPTIONS: {scaling_count} scaling actions, {rollback_count} rollback options, {config_count} config changes

Write a 3-4 sentence technical summary that:
1. States the SPECIFIC problem (e.g., "5xx errors spiked to 12% due to...")
2. Identifies the LIKELY CAUSE with evidence (e.g., "Correlated with deployment at 14:30 UTC...")
3. Recommends the EXACT action to take (e.g., "Scale to 4 instances" or "Rollback deployment v2.3.1")
4. Mentions any RISKS or things to monitor after the fix

Be direct and technical. Use specific numbers, service names, and metrics when available. No fluff."""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 350,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        content = result.get('content', [{}])[0].get('text', '')
        return content.strip()
    except Exception as e:
        print(f'[Summary] Bedrock error: {e}')
        # Fallback to rule-based summary
        return generate_fallback_summary(service, alarm_name, action_type, action_desc, severity, action_reasoning)


def generate_fallback_summary(service, alarm_name, action_type, action_desc, severity, reasoning=''):
    """Generate a developer-focused fallback summary without AI."""
    
    action_commands = {
        'scaling': f'aws autoscaling set-desired-capacity --auto-scaling-group-name {service}-asg --desired-capacity 4',
        'rollback': f'aws deploy stop-deployment --deployment-id <ID> --auto-rollback-enabled',
        'configuration_change': f'aws ssm put-parameter --name /{service}/config/<PARAM> --value <VALUE> --overwrite',
        'manual_intervention': f'aws logs tail /aws/lambda/{service} --follow'
    }
    
    action_labels = {
        'scaling': 'Scale horizontally',
        'rollback': 'Rollback deployment',
        'configuration_change': 'Update configuration',
        'manual_intervention': 'Manual investigation required'
    }
    
    severity_impact = {
        5: 'CRITICAL - Immediate action required. Service is down or severely degraded.',
        4: 'HIGH - Significant impact on users. Prioritize resolution.',
        3: 'MEDIUM - Noticeable degradation. Address within SLA.',
        2: 'LOW - Minor impact. Schedule for next maintenance window.',
        1: 'INFO - No immediate action needed. Monitor for changes.'
    }
    
    action = action_labels.get(action_type, 'Investigate manually')
    impact = severity_impact.get(severity, 'MEDIUM - Address promptly.')
    cmd = action_commands.get(action_type, '')
    
    summary = f"{impact} {alarm_name} triggered on {service}. "
    summary += f"Recommended: {action}. "
    if action_desc:
        summary += f"{action_desc} "
    if reasoning:
        summary += f"Evidence: {reasoning[:200]}..."
    
    return summary


def generate_smart_quick_actions(recommendations, service, alarm_name, root_cause_summary, agent_investigation):
    """
    Generate quick actions DIRECTLY from the actual remediation recommendations and investigation.
    Extracts real steps, commands, and findings - not generic templates.
    """
    actions = []
    
    # STEP 1: Extract runbook steps from recommendations (most actionable)
    for rec in recommendations:
        source = rec.get('source', '')
        description = rec.get('description', '')
        reasoning = rec.get('reasoning', '')
        category = rec.get('category', '')
        
        # Extract runbook steps
        if 'runbook' in source.lower():
            # Parse runbook steps from the description or reasoning
            import re
            steps_match = re.findall(r'(\d+)\.\s*([^0-9]+?)(?=\d+\.|$)', description + ' ' + reasoning)
            for step_num, step_text in steps_match[:3]:  # Top 3 runbook steps
                step_clean = step_text.strip().rstrip('.')
                if len(step_clean) > 10:  # Valid step
                    actions.append({
                        'label': f'📖 Runbook Step {step_num}: {step_clean[:50]}...',
                        'command': f'# {step_clean}',
                        'source': 'runbook',
                        'priority': 1
                    })
    
    # STEP 2: Extract specific metrics/thresholds from investigation
    if agent_investigation:
        import re
        
        # Extract queue depth values
        queue_matches = re.findall(r'queue\s*depth[:\s]*\(?(\d+)\)?', agent_investigation.lower())
        if queue_matches:
            depth = queue_matches[0]
            actions.append({
                'label': f'📊 Queue Depth was {depth} - Check Current',
                'command': f'aws sqs get-queue-attributes --queue-url https://sqs.us-east-1.amazonaws.com/${{AWS_ACCOUNT_ID}}/{service}-queue --attribute-names ApproximateNumberOfMessages',
                'source': 'investigation',
                'priority': 2
            })
        
        # Extract error counts from X-Ray
        error_match = re.search(r'Errors:\s*(\d+)', agent_investigation)
        fault_match = re.search(r'Faults:\s*(\d+)', agent_investigation)
        if error_match or fault_match:
            errors = error_match.group(1) if error_match else '0'
            faults = fault_match.group(1) if fault_match else '0'
            actions.append({
                'label': f'🔬 X-Ray: {errors} errors, {faults} faults - Get Traces',
                'command': f'aws xray get-trace-summaries --start-time $(date -u -d "1 hour ago" +%s) --end-time $(date -u +%s) --filter-expression "service(id(name: \\"{service}\\")) AND fault = true"',
                'source': 'xray',
                'priority': 2
            })
        
        # Extract latency values
        latency_match = re.search(r'latency[:\s]*(\d+)\s*ms', agent_investigation.lower())
        p99_match = re.search(r'P99[:\s]*latency[^0-9]*(\d+)\s*ms', agent_investigation, re.IGNORECASE)
        if p99_match:
            p99 = p99_match.group(1)
            actions.append({
                'label': f'⏱️ P99 Latency spiked to {p99}ms - Check Current',
                'command': f'aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Duration --dimensions Name=FunctionName,Value={service} --period 60 --statistics p99 --start-time $(date -u -d "30 minutes ago" +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)',
                'source': 'investigation',
                'priority': 2
            })
        
        # Extract non-compliant resource count
        noncompliant_match = re.search(r'Non-compliant resources:\s*(\d+)', agent_investigation)
        if noncompliant_match:
            count = noncompliant_match.group(1)
            actions.append({
                'label': f'⚠️ {count} Non-Compliant Resources - List Details',
                'command': f'aws configservice get-compliance-details-by-config-rule --config-rule-name lambda-function-public-access-prohibited --compliance-types NON_COMPLIANT',
                'source': 'config',
                'priority': 3
            })
        
        # Extract specific alarm names
        alarm_matches = re.findall(r'([A-Za-z]+-' + re.escape(service) + r')', agent_investigation)
        if alarm_matches:
            unique_alarms = list(set(alarm_matches))[:2]
            for alarm in unique_alarms:
                actions.append({
                    'label': f'🚨 Check Alarm: {alarm}',
                    'command': f'aws cloudwatch describe-alarms --alarm-names {alarm} --query "MetricAlarms[0].{{State:StateValue,Reason:StateReason,Threshold:Threshold}}"',
                    'source': 'investigation',
                    'priority': 3
                })
    
    # STEP 3: Add category-specific fix commands based on recommendations
    categories_found = set(r.get('category', '') for r in recommendations)
    
    if 'scaling' in categories_found:
        # Find the scaling recommendation details
        scaling_rec = next((r for r in recommendations if r.get('category') == 'scaling'), {})
        actions.append({
            'label': '🚀 SCALE OUT - Fix Capacity Issue',
            'command': f'aws autoscaling set-desired-capacity --auto-scaling-group-name {service}-asg --desired-capacity 4 && aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names {service}-asg --query "AutoScalingGroups[0].DesiredCapacity"',
            'source': 'remediation',
            'priority': 1
        })
    
    if 'configuration_change' in categories_found:
        config_rec = next((r for r in recommendations if r.get('category') == 'configuration_change'), {})
        actions.append({
            'label': '🔧 Review Config Compliance',
            'command': f'aws configservice get-compliance-summary-by-resource-type --resource-types AWS::Lambda::Function',
            'source': 'remediation',
            'priority': 2
        })
    
    if 'rollback' in categories_found:
        actions.append({
            'label': '↩️ Rollback Deployment',
            'command': f'aws deploy list-deployments --application-name {service} --deployment-group-name {service}-prod --max-items 3 && echo "Use: aws deploy stop-deployment --deployment-id <ID> --auto-rollback-enabled"',
            'source': 'remediation',
            'priority': 1
        })
    
    # STEP 4: Add root cause specific action
    if root_cause_summary:
        root_lower = root_cause_summary.lower()
        if 'queue' in root_lower or 'capacity' in root_lower or 'volume' in root_lower:
            actions.append({
                'label': '📈 Root Cause: Capacity - Increase Consumers',
                'command': f'aws lambda update-function-configuration --function-name {service} --reserved-concurrent-executions 100',
                'source': 'root_cause',
                'priority': 1
            })
        elif 'memory' in root_lower or 'oom' in root_lower:
            actions.append({
                'label': '💾 Root Cause: Memory - Increase Lambda Memory',
                'command': f'aws lambda update-function-configuration --function-name {service} --memory-size 1024',
                'source': 'root_cause',
                'priority': 1
            })
        elif 'timeout' in root_lower:
            actions.append({
                'label': '⏰ Root Cause: Timeout - Increase Timeout',
                'command': f'aws lambda update-function-configuration --function-name {service} --timeout 60',
                'source': 'root_cause',
                'priority': 1
            })
    
    # STEP 5: Always add diagnostic commands
    actions.append({
        'label': '📜 Tail Live Logs',
        'command': f'aws logs tail /aws/lambda/{service} --follow --since 5m',
        'source': 'diagnostic',
        'priority': 4
    })
    
    # Sort by priority and deduplicate
    actions.sort(key=lambda x: x.get('priority', 5))
    
    # Remove duplicates and limit
    seen_labels = set()
    unique_actions = []
    for action in actions:
        label_key = action['label'][:30]  # Use first 30 chars as key
        if label_key not in seen_labels:
            seen_labels.add(label_key)
            unique_actions.append({
                'label': action['label'],
                'command': action['command']
            })
    
    return unique_actions[:8]


def generate_quick_actions(action_type, service, alarm_name):
    """Generate developer-focused quick action commands based on the recommendation type."""
    
    actions = []
    
    if action_type == 'scaling':
        actions = [
            {'label': '📈 Scale Out (Double Capacity)', 'command': f'aws autoscaling set-desired-capacity --auto-scaling-group-name {service}-asg --desired-capacity 4'},
            {'label': '📊 Check Current CPU/Memory', 'command': f'aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=AutoScalingGroupName,Value={service}-asg --period 60 --statistics Average,Maximum --start-time $(date -u -d "30 minutes ago" +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)'},
            {'label': '🔍 View ASG Status', 'command': f'aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names {service}-asg --query "AutoScalingGroups[0].{{Desired:DesiredCapacity,Running:Instances[?LifecycleState==`InService`]|length(@),Min:MinSize,Max:MaxSize}}"'},
            {'label': '⚡ Check Target Group Health', 'command': f'aws elbv2 describe-target-health --target-group-arn $(aws elbv2 describe-target-groups --names {service}-tg --query "TargetGroups[0].TargetGroupArn" --output text)'},
            {'label': '📝 View Recent Scaling Activities', 'command': f'aws autoscaling describe-scaling-activities --auto-scaling-group-name {service}-asg --max-items 5'}
        ]
    elif action_type == 'rollback':
        actions = [
            {'label': '📋 List Recent Deployments', 'command': f'aws deploy list-deployments --application-name {service} --deployment-group-name {service}-prod --include-only-statuses Succeeded Failed --max-items 5'},
            {'label': '↩️ Rollback to Previous', 'command': f'aws deploy create-deployment --application-name {service} --deployment-group-name {service}-prod --revision revisionType=S3,s3Location={{bucket={service}-artifacts,key=previous-version.zip,bundleType=zip}}'},
            {'label': '🔍 Get Last Successful Deployment', 'command': f'aws deploy get-deployment --deployment-id $(aws deploy list-deployments --application-name {service} --deployment-group-name {service}-prod --include-only-statuses Succeeded --max-items 1 --query "deployments[0]" --output text)'},
            {'label': '⏸️ Stop Current Deployment', 'command': f'aws deploy stop-deployment --deployment-id <DEPLOYMENT_ID> --auto-rollback-enabled'},
            {'label': '📊 Check Deployment Status', 'command': f'aws deploy get-deployment --deployment-id <DEPLOYMENT_ID> --query "deploymentInfo.{{Status:status,ErrorInfo:errorInformation}}"'}
        ]
    elif action_type == 'configuration_change':
        actions = [
            {'label': '📋 List Current Config', 'command': f'aws ssm get-parameters-by-path --path /{service}/config --recursive --query "Parameters[*].{{Name:Name,Value:Value}}"'},
            {'label': '✏️ Update Parameter', 'command': f'aws ssm put-parameter --name /{service}/config/<PARAM_NAME> --value "<NEW_VALUE>" --type String --overwrite'},
            {'label': '🔄 Force Service Restart (ECS)', 'command': f'aws ecs update-service --cluster {service}-cluster --service {service} --force-new-deployment'},
            {'label': '🔄 Force Service Restart (Lambda)', 'command': f'aws lambda update-function-configuration --function-name {service} --environment "Variables={{RESTART_TRIGGER=$(date +%s)}}"'},
            {'label': '📝 View Config History', 'command': f'aws ssm get-parameter-history --name /{service}/config/<PARAM_NAME> --max-results 5'}
        ]
    else:
        actions = [
            {'label': '📜 Tail Live Logs', 'command': f'aws logs tail /aws/lambda/{service} --follow --since 10m'},
            {'label': '🔍 Search Error Logs', 'command': f'aws logs filter-log-events --log-group-name /aws/lambda/{service} --filter-pattern "ERROR" --start-time $(date -u -d "1 hour ago" +%s)000'},
            {'label': '📊 Check CloudWatch Alarms', 'command': f'aws cloudwatch describe-alarms --alarm-name-prefix {service} --state-value ALARM --query "MetricAlarms[*].{{Name:AlarmName,State:StateValue,Reason:StateReason}}"'},
            {'label': '🔬 Get X-Ray Traces', 'command': f'aws xray get-trace-summaries --start-time $(date -u -d "30 minutes ago" +%s) --end-time $(date -u +%s) --filter-expression "service(id(name: \\"{service}\\")) AND responseTime > 1"'},
            {'label': '📈 View Key Metrics', 'command': f'aws cloudwatch get-metric-data --metric-data-queries \'[{{"Id":"errors","MetricStat":{{"Metric":{{"Namespace":"AWS/Lambda","MetricName":"Errors","Dimensions":[{{"Name":"FunctionName","Value":"{service}"}}]}},"Period":60,"Stat":"Sum"}}}}]\' --start-time $(date -u -d "1 hour ago" +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)'}
        ]
    
    return actions


def store_summary(incident_id, summary):
    """Store the summary in both DynamoDB tables."""
    try:
        # Store in incidents table (for backward compatibility)
        table = dynamodb.Table(INCIDENTS_TABLE)
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET remediation_summary = :summary, summary_generated_at = :ts',
            ExpressionAttributeValues={
                ':summary': json.dumps(summary),
                ':ts': datetime.utcnow().isoformat() + 'Z'
            }
        )
        print(f'[Summary] Stored summary in incidents table for {incident_id}')
        
        # Store in dedicated AI reasoning table
        reasoning_table = dynamodb.Table(AI_REASONING_TABLE)
        reasoning_item = {
            'incident_id': incident_id,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'service': summary.get('service', 'unknown'),
            'alarm_name': summary.get('alarm_name', ''),
            'severity': summary.get('severity', 3),
            'business_impact': summary.get('business_impact', 5),
            'ai_summary': summary.get('ai_summary', ''),
            'root_cause': summary.get('root_cause', ''),
            'investigation_summary': summary.get('investigation_summary', ''),
            'data_sources_analyzed': summary.get('data_sources_analyzed', 0),
            'total_recommendations': summary.get('total_recommendations', 0),
            'recommendation_breakdown': json.dumps(summary.get('recommendation_breakdown', {})),
            'recommended_action': json.dumps(summary.get('recommended_action', {})),
            'quick_actions': json.dumps(summary.get('quick_actions', [])),
            'ttl': int((datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60))  # 90 days TTL
        }
        reasoning_table.put_item(Item=reasoning_item)
        print(f'[Summary] Stored summary in AI reasoning table for {incident_id}')
        
    except Exception as e:
        print(f'[Summary] Failed to store summary: {e}')
'''

def create_lambda():
    """Create or update the Lambda function."""
    
    # Create zip file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('index.py', LAMBDA_CODE)
    zip_buffer.seek(0)
    
    # Get the role ARN - use the remediation recommendation role
    role_arn = 'arn:aws:iam::193786182229:role/outageshield-remediation-rec-role-dev'
    
    try:
        # Try to update existing function
        response = lambda_client.update_function_code(
            FunctionName=LAMBDA_NAME,
            ZipFile=zip_buffer.read()
        )
        print(f'✓ Lambda {LAMBDA_NAME} updated!')
        print(f'  Last modified: {response["LastModified"]}')
    except lambda_client.exceptions.ResourceNotFoundException:
        # Create new function
        zip_buffer.seek(0)
        response = lambda_client.create_function(
            FunctionName=LAMBDA_NAME,
            Runtime='python3.12',
            Role=role_arn,
            Handler='index.lambda_handler',
            Code={'ZipFile': zip_buffer.read()},
            Timeout=90,
            MemorySize=256,
            Environment={
                'Variables': {
                    'MODEL_ID': 'anthropic.claude-3-haiku-20240307-v1:0',
                    'INCIDENTS_TABLE': 'outageshield-incidents-dev',
                    'AI_REASONING_TABLE': 'outageshield-ai-reasoning-dev'
                }
            }
        )
        print(f'✓ Lambda {LAMBDA_NAME} created!')
        print(f'  ARN: {response["FunctionArn"]}')


if __name__ == '__main__':
    print('=' * 60)
    print('Creating Remediation Summary Lambda')
    print('=' * 60)
    print()
    print('This Lambda summarizes investigation and remediation findings')
    print('to suggest the most effective way to remediate the issue.')
    print()
    print('Features:')
    print('  ✓ Analyzes all recommendations to find the best one')
    print('  ✓ Generates AI-powered summary using Bedrock')
    print('  ✓ Provides quick action commands')
    print('  ✓ Stores summary in DynamoDB')
    print()
    
    create_lambda()
    
    print()
    print('Next: Update the Step Functions workflow to include this Lambda')
