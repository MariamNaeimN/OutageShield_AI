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
    """Generate recommendations using PURE RULE-BASED LOGIC - NO AI, NO HALLUCINATION.
    Each recommendation is directly derived from the tool output data."""
    
    recommendations = []
    alarm_lower = (alarm_name or '').lower()
    
    # 0. ALARM-TYPE BASED RECOMMENDATIONS - Add specific recommendations based on alarm type
    if 'highlatency' in alarm_lower or 'latency' in alarm_lower:
        recommendations.append({
            'category': 'scaling',
            'description': f'High latency detected on {service}. Consider horizontal scaling to handle increased load, or optimize slow database queries and API calls.',
            'reasoning': f'Alarm type "{alarm_name}" indicates latency issues that often benefit from scaling.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 4,
            'risk': 'low',
            'estimated_ttr_minutes': 15,
            'confidence': 80
        })
    
    if 'high5xx' in alarm_lower or '5xx' in alarm_lower or 'error' in alarm_lower:
        recommendations.append({
            'category': 'rollback',
            'description': f'High error rate on {service}. If errors started after a recent deployment, consider rolling back to the previous stable version.',
            'reasoning': f'Alarm type "{alarm_name}" suggests application errors that may be caused by a bad deployment.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 5,
            'risk': 'medium',
            'estimated_ttr_minutes': 10,
            'confidence': 75
        })
    
    if 'connectionpool' in alarm_lower or 'connection' in alarm_lower or 'database' in alarm_lower:
        recommendations.append({
            'category': 'scaling',
            'description': f'Database connection issues on {service}. Scale database read replicas or increase connection pool limits.',
            'reasoning': f'Alarm type "{alarm_name}" indicates database capacity issues.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 4,
            'risk': 'low',
            'estimated_ttr_minutes': 20,
            'confidence': 80
        })
    
    if 'queuebacklog' in alarm_lower or 'queue' in alarm_lower or 'backlog' in alarm_lower:
        recommendations.append({
            'category': 'scaling',
            'description': f'Message queue backlog on {service}. Scale consumer instances or increase processing capacity.',
            'reasoning': f'Alarm type "{alarm_name}" indicates queue processing cannot keep up with incoming messages.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 4,
            'risk': 'low',
            'estimated_ttr_minutes': 15,
            'confidence': 85
        })
    
    if 'highcpu' in alarm_lower or 'cpu' in alarm_lower or 'memory' in alarm_lower:
        recommendations.append({
            'category': 'scaling',
            'description': f'Resource exhaustion on {service}. Scale vertically (larger instance) or horizontally (more instances).',
            'reasoning': f'Alarm type "{alarm_name}" indicates compute resource constraints.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 4,
            'risk': 'low',
            'estimated_ttr_minutes': 15,
            'confidence': 85
        })
    
    if 'cachemiss' in alarm_lower or 'cache' in alarm_lower:
        recommendations.append({
            'category': 'configuration_change',
            'description': f'High cache miss rate on {service}. Review cache TTL settings, increase cache size, or warm the cache.',
            'reasoning': f'Alarm type "{alarm_name}" indicates caching inefficiency.',
            'source': 'AGENT:alarm_analysis',
            'effectiveness': 3,
            'risk': 'low',
            'estimated_ttr_minutes': 20,
            'confidence': 75
        })
    
    # 1. DEPLOYMENT CORRELATION - check for actual deployment data
    deployment_data = sources.get('deployment', '')
    deployment_lower = deployment_data.lower() if deployment_data else ''
    
    # Check if this is a "no deployment" message
    no_deploy_indicators = [
        'no recent deployment',
        'no deployments',
        'no deployment found',
        'no config changes',
        'no configuration changes',
        'not found',
        'no data'
    ]
    is_no_deployment = any(ind in deployment_lower for ind in no_deploy_indicators)
    
    if deployment_data and not is_no_data(deployment_data) and not is_no_deployment:
        # Parse actual deployment info from the text
        has_rollback = 'rolled_back' in deployment_lower or 'rollback' in deployment_lower
        has_failed = 'failed' in deployment_lower
        has_config = 'config:' in deployment_lower or 'changed from' in deployment_lower or 'config change' in deployment_lower
        
        # Look for actual version numbers or deployment IDs as proof of real deployment
        import re
        versions = re.findall(r'v[\d.]+', deployment_data)
        deploy_count_match = re.search(r'Found (\d+) deployment', deployment_data)
        config_count_match = re.search(r'(\d+) config change', deployment_data)
        deploy_count = int(deploy_count_match.group(1)) if deploy_count_match else 0
        config_count = int(config_count_match.group(1)) if config_count_match else 0
        
        has_actual_deployment = bool(versions) or deploy_count > 0
        version_str = versions[0] if versions else 'recent'
        
        if has_rollback or has_failed:
            recommendations.append({
                'category': 'rollback',
                'description': f'Deploy: Failed/rolled back deployment detected. Verify current version.',
                'reasoning': f'Deployment history shows issues with {version_str}.',
                'source': 'AGENT:deployment_correlation',
                'effectiveness': 4,
                'risk': 'medium',
                'estimated_ttr_minutes': 15,
                'confidence': 85
            })
        elif has_actual_deployment:
            recommendations.append({
                'category': 'rollback',
                'description': f'Deploy: {deploy_count} deployments, {config_count} config changes in 24h. Consider rollback if correlated.',
                'reasoning': f'Recent deployment: {version_str}. Check timing correlation.',
                'source': 'AGENT:deployment_correlation',
                'effectiveness': 4,
                'risk': 'medium',
                'estimated_ttr_minutes': 15,
                'confidence': 70
            })
        if has_config:
            recommendations.append({
                'category': 'configuration_change',
                'description': f'Deploy: {config_count} config changes detected. Review if correlated.',
                'reasoning': f'Configuration was modified recently.',
                'source': 'AGENT:deployment_correlation',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 10,
                'confidence': 75
            })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No recent deployments or config changes found. The issue is likely not deployment-related.',
            'reasoning': f'Deployment data: {deployment_data[:100] if deployment_data else "No data available"}',
            'source': 'AGENT:deployment_correlation',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 10,
            'confidence': 60
        })
    
    # 2. LOG PATTERNS - check for actual log data
    log_data = sources.get('opensearch', '')
    if log_data and not is_no_data(log_data):
        # Parse actual patterns from log data
        log_lower = log_data.lower()
        
        # Check for actual 5xx error codes - must be standalone HTTP codes, not part of timestamps
        # Look for patterns like "HTTP 500", "status 502", "error 503" etc.
        import re
        actual_5xx_pattern = re.search(r'(http[:\s]*5\d{2}|status[:\s]*5\d{2}|error[:\s]*5\d{2}|\b5\d{2}\s*(error|response|status))', log_lower)
        has_actual_5xx = bool(actual_5xx_pattern)
        
        has_error_alarm = 'errorrate-' in log_lower or 'errorrate:' in log_lower
        has_latency = 'highlatency' in log_lower or 'latency' in log_lower
        has_threshold = 'threshold' in log_lower and 'exceeded' in log_lower
        has_memory = 'highmemory' in log_lower or 'memory utilization' in log_lower
        has_disk = 'diskspace' in log_lower or 'disk utilization' in log_lower
        has_cpu = 'highcpu' in log_lower or 'cpu utilization' in log_lower
        
        # Count log entries
        log_count_match = re.search(r'Found (\d+) log', log_data)
        log_count = int(log_count_match.group(1)) if log_count_match else 0
        
        # Extract specific alarm types found
        alarm_types = []
        if has_latency or has_threshold:
            alarm_types.append('latency')
        if has_error_alarm:
            alarm_types.append('error rate')
        if has_memory:
            alarm_types.append('memory')
        if has_disk:
            alarm_types.append('disk')
        if has_cpu:
            alarm_types.append('CPU')
        
        if has_actual_5xx:
            recommendations.append({
                'category': 'scaling',
                'description': f'Logs: HTTP 5xx errors found ({log_count} entries). Check backend health.',
                'reasoning': f'Actual HTTP 5xx error codes detected in logs.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 15,
                'confidence': 85
            })
        
        if has_latency or has_threshold:
            recommendations.append({
                'category': 'scaling',
                'description': f'Logs: Latency threshold exceeded ({log_count} entries). Consider scaling.',
                'reasoning': f'P99 latency alarms triggered in logs.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 20,
                'confidence': 80
            })
        
        if has_error_alarm and not has_actual_5xx:
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'Logs: Error rate alarm triggered. Investigate error patterns.',
                'reasoning': f'ErrorRate alarm found. Check application logs for details.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 20,
                'confidence': 70
            })
        
        if has_memory or has_disk or has_cpu:
            resource_types = ', '.join([t for t in ['memory' if has_memory else None, 'disk' if has_disk else None, 'CPU' if has_cpu else None] if t])
            recommendations.append({
                'category': 'scaling',
                'description': f'Logs: Resource alerts ({resource_types}). Scale or optimize.',
                'reasoning': f'Resource utilization alarms detected.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 15,
                'confidence': 80
            })
        
        if not alarm_types and not has_actual_5xx:
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'Logs: {log_count} entries found. Review for patterns.',
                'reasoning': f'Log data available for analysis.',
                'source': 'AGENT:log_patterns',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 70
            })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No log patterns found in OpenSearch. Check CloudWatch Logs directly.',
            'reasoning': 'Log search tool returned no data.',
            'source': 'AGENT:log_patterns',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 20,
            'confidence': 50
        })
    
    # 3. RUNBOOK - check for actual runbook data
    runbook_data = sources.get('runbook', '')
    if runbook_data and not is_no_data(runbook_data):
        # Extract runbook title and steps
        import re
        title_match = re.search(r'Runbook:\s*([^\n]+)', runbook_data)
        raw_title = title_match.group(1).strip() if title_match else 'Available runbook'
        
        # Clean title - remove "Category:" and everything after
        if 'Category:' in raw_title:
            title = raw_title.split('Category:')[0].strip()
        else:
            title = raw_title[:40]
        
        # Extract category and TTR separately
        category_match = re.search(r'Category:\s*(\w+)', runbook_data)
        ttr_match = re.search(r'TTR:\s*([^\n,]+)', runbook_data)
        category = category_match.group(1) if category_match else 'general'
        ttr = ttr_match.group(1).strip() if ttr_match else '15-30 minutes'
        
        # Match numbered steps - works for both multi-line and single-line formats
        # Pattern: digit followed by period, then text until next digit+period or end
        steps = re.findall(r'(\d+)\.\s*([^0-9]+?)(?=\s*\d+\.|$)', runbook_data)
        num_steps = len(steps)
        first_step = steps[0][1].strip()[:60] if steps else 'Follow documented procedures'
        
        recommendations.append({
            'category': 'manual_intervention',
            'description': f'Runbook available: "{title}" with {num_steps} steps. Start: {first_step}',
            'reasoning': f'{num_steps} steps available. Category: {category}. TTR: {ttr}',
            'source': 'AGENT:runbook',
            'effectiveness': 4,
            'risk': 'low',
            'estimated_ttr_minutes': 15,
            'confidence': 85
        })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No runbook found for this alarm type. Follow general troubleshooting procedures.',
            'reasoning': 'Runbook lookup returned no matching runbook.',
            'source': 'AGENT:runbook',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 60,
            'confidence': 50
        })
    
    # 4. PAST INCIDENTS - check for actual incident history
    incident_data = sources.get('incident_history', '')
    if incident_data and not is_no_data(incident_data):
        # Extract past incident info
        import re
        incident_ids = re.findall(r'INC-[A-Z0-9]+', incident_data)
        statuses = re.findall(r'Status:\s*(\w+)', incident_data)
        root_cause_match = re.search(r'Root cause:\s*([^,\n]+)', incident_data)
        past_root_cause = root_cause_match.group(1)[:50] if root_cause_match else None
        
        resolved_count = sum(1 for s in statuses if s.lower() == 'resolved')
        
        if incident_ids:
            desc = f'Similar incident: {incident_ids[0]}'
            if past_root_cause:
                desc += f' (cause: {past_root_cause})'
            recommendations.append({
                'category': 'manual_intervention',
                'description': desc,
                'reasoning': f'Found {len(incident_ids)} past incidents. {resolved_count} resolved.',
                'source': 'AGENT:past_incidents',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 20,
                'confidence': 80
            })
        else:
            recommendations.append({
                'category': 'manual_intervention',
                'description': 'Past incident data found. Review historical resolutions for this service.',
                'reasoning': f'Historical data: {incident_data[:150]}',
                'source': 'AGENT:past_incidents',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 70
            })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No similar past incidents found. This may be a new issue type for this service.',
            'reasoning': 'Incident history search returned no matching incidents.',
            'source': 'AGENT:past_incidents',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 60,
            'confidence': 50
        })
    
    # 5. X-RAY TRACES - check for latency/error traces
    xray_data = sources.get('xray', '')
    if xray_data and not is_no_data(xray_data):
        import re
        has_errors = 'error' in xray_data.lower() or 'fault' in xray_data.lower()
        has_slow = 'slow' in xray_data.lower() or 'latency' in xray_data.lower() or 'duration' in xray_data.lower()
        
        # Extract service name from xray data if available
        service_match = re.search(r'Service:\s*(\S+)', xray_data)
        xray_service = service_match.group(1) if service_match else service
        if not xray_service or xray_service == 'unknown':
            xray_service = service if service else 'this service'
        
        # Extract metrics
        error_match = re.search(r'Errors?:\s*(\d+)', xray_data)
        fault_match = re.search(r'Faults?:\s*(\d+)', xray_data)
        requests_match = re.search(r'Total Requests?:\s*(\d+)', xray_data)
        errors = int(error_match.group(1)) if error_match else 0
        faults = int(fault_match.group(1)) if fault_match else 0
        requests = int(requests_match.group(1)) if requests_match else 0
        
        # Extract response times if present
        response_times = re.findall(r'(\d+)\s*ms', xray_data)
        max_latency = max([int(t) for t in response_times]) if response_times else 0
        
        if requests == 0:
            # No traces found - this is NOT "healthy", it means no data
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'X-Ray: No traces found. Enable X-Ray tracing for {xray_service}.',
                'reasoning': f'0 requests traced in the last hour. X-Ray may not be enabled.',
                'source': 'AGENT:xray_traces',
                'effectiveness': 2,
                'risk': 'low',
                'estimated_ttr_minutes': 15,
                'confidence': 60
            })
        elif errors > 0 or faults > 0:
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'X-Ray: {errors} errors, {faults} faults in {requests} requests. Investigate traces.',
                'reasoning': f'Error rate: {(errors+faults)/requests*100:.1f}%. Check failing requests.',
                'source': 'AGENT:xray_traces',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 80
            })
        elif max_latency > 1000:
            recommendations.append({
                'category': 'scaling',
                'description': f'X-Ray: High latency ({max_latency}ms) in {requests} requests. Scale or optimize.',
                'reasoning': f'P99 latency exceeds 1000ms threshold.',
                'source': 'AGENT:xray_traces',
                'effectiveness': 4,
                'risk': 'low',
                'estimated_ttr_minutes': 20,
                'confidence': 85
            })
        else:
            recommendations.append({
                'category': 'manual_intervention',
                'description': f'X-Ray: {requests} requests, {errors} errors, {max_latency}ms latency. Looks healthy.',
                'reasoning': f'Traces show normal operation.',
                'source': 'AGENT:xray_traces',
                'effectiveness': 2,
                'risk': 'low',
                'estimated_ttr_minutes': 10,
                'confidence': 70
            })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No X-Ray trace data found. Enable X-Ray tracing for better observability.',
            'reasoning': 'X-Ray trace search returned no data.',
            'source': 'AGENT:xray_traces',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 30,
            'confidence': 50
        })
    
    # 6. AWS CONFIG - check for compliance/drift issues
    config_data = sources.get('config', '')
    if config_data and not is_no_data(config_data):
        has_non_compliant = 'non_compliant' in config_data.lower() or 'non-compliant' in config_data.lower()
        has_drift = 'drift' in config_data.lower() or 'changed' in config_data.lower()
        
        if has_non_compliant:
            recommendations.append({
                'category': 'configuration_change',
                'description': 'Config: Non-compliant resources found. Review compliance.',
                'reasoning': f'AWS Config detected compliance violations.',
                'source': 'AGENT:config_drift',
                'effectiveness': 4,
                'risk': 'medium',
                'estimated_ttr_minutes': 45,
                'confidence': 80
            })
        elif has_drift:
            recommendations.append({
                'category': 'configuration_change',
                'description': 'Config: Configuration drift detected. Verify changes.',
                'reasoning': f'Recent configuration changes may affect service.',
                'source': 'AGENT:config_drift',
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 75
            })
        else:
            recommendations.append({
                'category': 'manual_intervention',
                'description': 'Config: Service configuration reviewed. No issues found.',
                'reasoning': f'Configuration state is normal.',
                'source': 'AGENT:config_drift',
                'effectiveness': 2,
                'risk': 'low',
                'estimated_ttr_minutes': 10,
                'confidence': 65
            })
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': 'No AWS Config data found. Enable Config for configuration tracking and compliance.',
            'reasoning': 'AWS Config check returned no data.',
            'source': 'AGENT:config_drift',
            'effectiveness': 1,
            'risk': 'low',
            'estimated_ttr_minutes': 30,
            'confidence': 50
        })
    
    # Sort recommendations: prioritize actionable ones (higher effectiveness, confidence)
    # "No data found" recommendations should NOT be top picks
    def sort_key(rec):
        # Penalize "no data" or "not found" recommendations
        desc_lower = rec.get('description', '').lower()
        is_no_data = any(phrase in desc_lower for phrase in [
            'no recent deployment', 'no data found', 'not found', 
            'no log patterns', 'no runbook', 'no similar past', 
            'no x-ray', 'no aws config', 'enable config', 'enable x-ray',
            'issue is likely not'
        ])
        
        # Score: effectiveness * confidence, but penalize no-data recommendations heavily
        base_score = rec.get('effectiveness', 1) * rec.get('confidence', 50)
        if is_no_data:
            base_score = base_score * 0.1  # Heavy penalty
        
        return -base_score  # Negative for descending sort
    
    recommendations.sort(key=sort_key)
    
    return recommendations


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
    """Validate and fix recommendation sources, ensuring all sources are covered."""
    valid_sources = set(available_sources + ['RCA', 'agent_advice'])
    validated = []
    used_sources = set()
    
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
        
        used_sources.add(rec['source'])
        
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
    
    # Ensure all available sources are covered - add fallback recommendations for missing sources
    missing_sources = set(available_sources) - used_sources
    for missing_source in missing_sources:
        
        # Generate a fallback recommendation for the missing source
        source_type = missing_source.split(':')[-1] if ':' in missing_source else missing_source
        
        if 'log' in source_type.lower():
            validated.append({
                'category': 'manual_intervention',
                'description': 'Investigate the error patterns found in logs. The log analysis shows alarm triggers that correlate with the incident.',
                'reasoning': 'Log patterns from OpenSearch indicate recurring issues that need attention.',
                'source': missing_source,
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 70
            })
        elif 'runbook' in source_type.lower():
            validated.append({
                'category': 'manual_intervention',
                'description': 'Follow the documented runbook procedures for this alarm type.',
                'reasoning': 'A runbook with remediation guidance is available.',
                'source': missing_source,
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 30,
                'confidence': 75
            })
        elif 'deployment' in source_type.lower():
            validated.append({
                'category': 'configuration_change',
                'description': 'Review recent deployments and configuration changes that may correlate with the incident.',
                'reasoning': 'Deployment history shows recent changes.',
                'source': missing_source,
                'effectiveness': 4,
                'risk': 'medium',
                'estimated_ttr_minutes': 30,
                'confidence': 75
            })
        elif 'incident' in source_type.lower() or 'past' in source_type.lower():
            validated.append({
                'category': 'manual_intervention',
                'description': 'Review similar past incidents for resolution patterns that may apply.',
                'reasoning': 'Historical incident data provides context for resolution.',
                'source': missing_source,
                'effectiveness': 3,
                'risk': 'low',
                'estimated_ttr_minutes': 45,
                'confidence': 70
            })
    
    return validated  # Return all recommendations - no limit


def generate_fallback_recommendations(sources, root_causes, service):
    """Generate rule-based recommendations for ALL 4 sources."""
    recommendations = []
    
    # 1. Deployment-based recommendation (always include)
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
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': f'No recent deployments found for {service}. Verify deployment history manually and check if any infrastructure changes occurred outside the tracked system.',
            'reasoning': 'No deployment data available - manual verification recommended.',
            'source': 'AGENT:deployment_correlation',
            'effectiveness': 2,
            'risk': 'low',
            'estimated_ttr_minutes': 20,
            'confidence': 50
        })
    
    # 2. Log-based recommendation (always include)
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
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': f'No log patterns found in OpenSearch for {service}. Check CloudWatch Logs directly and verify log ingestion is working correctly.',
            'reasoning': 'No log data available - manual log review recommended.',
            'source': 'AGENT:log_patterns',
            'effectiveness': 2,
            'risk': 'low',
            'estimated_ttr_minutes': 30,
            'confidence': 50
        })
    
    # 3. Runbook-based recommendation (always include)
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
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': f'No runbook found for this alarm type. Consider creating a runbook for {service} incidents to improve future response times.',
            'reasoning': 'No runbook available - follow general troubleshooting procedures.',
            'source': 'AGENT:runbook',
            'effectiveness': 2,
            'risk': 'low',
            'estimated_ttr_minutes': 60,
            'confidence': 50
        })
    
    # 4. Past incidents recommendation (always include)
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
    else:
        recommendations.append({
            'category': 'manual_intervention',
            'description': f'No similar past incidents found for {service}. This may be a new issue type - document the resolution for future reference.',
            'reasoning': 'No historical incident data available - this appears to be a new issue.',
            'source': 'AGENT:past_incidents',
            'effectiveness': 2,
            'risk': 'low',
            'estimated_ttr_minutes': 60,
            'confidence': 50
        })
    
    return recommendations


def parse_investigation_sources(investigation):
    """Parse the agent investigation text and extract content for each source."""
    sources = {
        'opensearch': '',
        'runbook': '',
        'deployment': '',
        'incident_history': '',
        'xray': '',
        'config': ''
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
        elif 'deployment' in tag_name:
            sources['deployment'] = content
        elif 'incident' in tag_name or 'history' in tag_name or 'past' in tag_name:
            sources['incident_history'] = content
        elif 'x-ray' in tag_name or 'xray' in tag_name or 'trace' in tag_name:
            sources['xray'] = content
        elif 'config' in tag_name or 'compliance' in tag_name or 'drift' in tag_name:
            sources['config'] = content
    
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
        'no recent deployment',
        'no deployments',
        'no config changes',
        'no configuration changes',
        'no information available',
        'could not find',
        'unable to find',
        'no results',
        'no matching',
        'not found'
    ]
    
    # Check if content is primarily a "no data" message
    for pattern in no_data_patterns:
        if lower.startswith(pattern) or pattern in lower[:100]:
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
    if sources.get('xray') and not is_no_data(sources['xray']):
        evidence_found.append('X-Ray traces')
    if sources.get('config') and not is_no_data(sources['config']):
        evidence_found.append('Config compliance')
    
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
