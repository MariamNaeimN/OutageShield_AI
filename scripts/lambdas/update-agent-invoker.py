"""Update agent-invoker Lambda to DIRECTLY call all 6 tools.
Instead of relying on Bedrock Agent to decide which tools to call,
we call the agent-actions Lambda directly for each tool."""
import boto3
import zipfile
import io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = r'''import json
import boto3
import os

lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

AGENT_ACTIONS_LAMBDA = os.environ.get('AGENT_ACTIONS_LAMBDA', 'outageshield-agent-actions-dev')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')

def lambda_handler(event, context):
    """
    Directly call ALL 6 investigation tools via the agent-actions Lambda.
    This guarantees all tools are called - no reliance on agent autonomy.
    """
    signal = event.get('signal', {})
    incident_id = signal.get('signal_id', '')
    service = signal.get('service', 'unknown')
    alarm_name = signal.get('alarm_name', '')

    step3 = event.get('step3', {})
    root_causes = step3.get('root_causes', [])
    root_cause = root_causes[0].get('description', 'Unknown') if root_causes else 'Unknown'

    # Extract alarm type for runbook lookup
    alarm_type = alarm_name.split('-')[0] if '-' in alarm_name else alarm_name
    if alarm_type.startswith('Outage signal') or alarm_type == 'Outage':
        if 'latency' in root_cause.lower():
            alarm_type = 'HighLatency'
        elif '5xx' in root_cause.lower() or 'error' in root_cause.lower():
            alarm_type = 'High5xxRate'
        elif 'memory' in root_cause.lower():
            alarm_type = 'MemoryPressure'
        elif 'cpu' in root_cause.lower():
            alarm_type = 'HighCPU'
        else:
            alarm_type = 'HighLatency'

    print(f"Direct tool investigation for {incident_id}: service={service}, alarm_type={alarm_type}")

    # Call ALL 6 tools directly
    tool_results = {}
    
    # Tool 1: Search Incident History
    print("Calling Tool 1: searchIncidentHistory...")
    tool_results['incident_history'] = call_tool('/search-incidents', {'service': service})
    
    # Tool 2: Search Logs
    print("Calling Tool 2: searchLogs...")
    tool_results['logs'] = call_tool('/search-logs', {'service': service, 'time_range': '6h'})
    
    # Tool 3: Get Runbook
    print("Calling Tool 3: getRunbook...")
    tool_results['runbook'] = call_tool('/get-runbook', {'service': service, 'alarm_type': alarm_type})
    
    # Tool 4: Check Deployments
    print("Calling Tool 4: checkDeployments...")
    tool_results['deployments'] = call_tool('/check-deployments', {'service': service, 'hours_back': '24'})
    
    # Tool 5: Search X-Ray Traces
    print("Calling Tool 5: searchTraces...")
    tool_results['xray'] = call_tool('/search-traces', {'service': service, 'time_range': '1h'})
    
    # Tool 6: Check Config Drift
    print("Calling Tool 6: checkConfigDrift...")
    tool_results['config'] = call_tool('/check-config-drift', {'service': service})

    # Count successful tool calls
    tools_called = sum(1 for v in tool_results.values() if v is not None)
    missing_tools = [k for k, v in tool_results.items() if v is None]
    
    print(f"Tools called: {tools_called}/6, Missing: {missing_tools}")

    # Format investigation from tool results
    investigation = format_tool_results(tool_results, service, alarm_name, root_cause)
    
    print(f"Investigation formatted: {len(investigation)} chars")

    # Update DynamoDB if we have an incident ID
    if incident_id:
        try:
            table = dynamodb.Table(INCIDENTS_TABLE)
            table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression='SET agent_investigation = :ai',
                ExpressionAttributeValues={':ai': investigation[:4000]}
            )
            print(f"Updated DynamoDB for {incident_id}")
        except Exception as e:
            print(f"DynamoDB update failed: {e}")

    return {
        'statusCode': 200,
        'incident_id': incident_id,
        'investigation': investigation[:4000],
        'status': 'completed',
        'tools_called': tools_called,
        'missing_tools': missing_tools
    }


def call_tool(api_path, params):
    """Call a tool via the agent-actions Lambda."""
    try:
        payload = {
            'actionGroup': 'IncidentInvestigation',
            'apiPath': api_path,
            'parameters': [{'name': k, 'value': str(v)} for k, v in params.items()]
        }
        
        response = lambda_client.invoke(
            FunctionName=AGENT_ACTIONS_LAMBDA,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        # Extract the actual result from the response
        if 'response' in result:
            body = result['response'].get('responseBody', {})
            json_body = body.get('application/json', {}).get('body', '{}')
            return json.loads(json_body) if isinstance(json_body, str) else json_body
        
        return result
        
    except Exception as e:
        print(f"Tool call failed for {api_path}: {e}")
        return None


def format_tool_results(tool_results, service, alarm_name, root_cause):
    """Format investigation from ALL tool results."""
    sections = []

    # Section 1: Incident History
    sections.append("[Source: Incident History DB]")
    ih = tool_results.get('incident_history')
    if ih:
        incidents = ih.get('incidents', [])
        total = ih.get('total_past_incidents', len(incidents))
        if incidents:
            sections.append(f"Found {total} past incidents for {service}:")
            for inc in incidents[:5]:
                inc_id = inc.get('incident_id', 'Unknown')
                title = inc.get('title', 'No title')
                rc = inc.get('root_cause', 'Unknown')
                status = inc.get('status', 'Unknown')
                sections.append(f"- {inc_id}: {title} (Root cause: {rc}, Status: {status})")
        else:
            sections.append(f"No past incidents found for {service}.")
    else:
        sections.append("Tool call failed.")

    # Section 2: OpenSearch Logs
    sections.append("\n[Source: OpenSearch Logs]")
    logs = tool_results.get('logs')
    if logs:
        patterns = logs.get('patterns', [])
        data_source = logs.get('data_source', 'Unknown')
        total = logs.get('total_log_entries', len(patterns))
        if patterns:
            sections.append(f"Found {total} log entries from {data_source}:")
            for log in patterns[:5]:
                alarm = log.get('alarm_name', 'Unknown')
                msg = log.get('message', '')[:100]
                ts = log.get('timestamp', '')
                severity = log.get('severity', 'unknown')
                sections.append(f"- [{severity}] {alarm}: {msg} ({ts})")
        else:
            sections.append(f"No log entries found. Data source: {data_source}")
    else:
        sections.append("Tool call failed.")

    # Section 3: Runbook
    sections.append("\n[Source: Runbook DB]")
    rb_result = tool_results.get('runbook')
    if rb_result:
        rb = rb_result.get('runbook', {})
        if rb and rb.get('title'):
            sections.append(f"Runbook: {rb.get('title', 'Unknown')}")
            sections.append(f"Category: {rb.get('category', 'Unknown')}, Estimated TTR: {rb.get('estimated_ttr', 'Unknown')}")
            steps = rb.get('steps', [])
            if steps:
                sections.append("Steps:")
                for i, step in enumerate(steps[:5], 1):
                    sections.append(f"  {i}. {step}")
        else:
            alarm_type = rb_result.get('alarm_type', 'Unknown')
            sections.append(f"No specific runbook found for alarm type: {alarm_type}")
    else:
        sections.append("Tool call failed.")

    # Section 4: Deployment History
    sections.append("\n[Source: Deployment History]")
    deps = tool_results.get('deployments')
    if deps:
        deployments = deps.get('recent_deployments', deps.get('deployments', []))
        config_changes = deps.get('config_changes', [])
        total_deps = deps.get('total_deployments', len(deployments))
        total_cfg = deps.get('total_config_changes', len(config_changes))
        data_source = deps.get('data_source', 'DynamoDB')
        
        sections.append(f"Data source: {data_source}")
        
        if deployments or config_changes:
            sections.append(f"Found {total_deps} deployments and {total_cfg} config changes in last 24h:")
            for dep in deployments[:3]:
                dep_id = dep.get('deployment_id', 'Unknown')
                version = dep.get('version', 'Unknown')
                prev_version = dep.get('previous_version', '')
                status = dep.get('status', 'Unknown')
                changes = dep.get('changes', '')[:80]
                ts = dep.get('timestamp', '')
                deployed_by = dep.get('deployed_by', 'unknown')
                sections.append(f"- Deploy {dep_id}: v{prev_version} -> v{version} ({status})")
                sections.append(f"  Time: {ts}, By: {deployed_by}")
                if changes:
                    sections.append(f"  Changes: {changes}")
            for cfg in config_changes[:3]:
                param = cfg.get('parameter', 'Unknown')
                old_val = cfg.get('old_value', '')
                new_val = cfg.get('new_value', '')
                ts = cfg.get('timestamp', '')
                changed_by = cfg.get('changed_by', 'unknown')
                sections.append(f"- Config Change: {param}")
                sections.append(f"  Value: {old_val} -> {new_val}")
                sections.append(f"  Time: {ts}, By: {changed_by}")
        else:
            sections.append("No recent deployments or config changes found in the last 24 hours.")
    else:
        sections.append("Tool call failed.")

    # Section 5: X-Ray Traces
    sections.append("\n[Source: X-Ray Traces]")
    xray = tool_results.get('xray')
    if xray:
        error_traces = xray.get('error_traces', [])
        slow_traces = xray.get('slow_traces', [])
        service_stats = xray.get('service_stats', {})
        
        if service_stats:
            sections.append(f"Service: {service_stats.get('name', service)}")
            sections.append(f"Type: {service_stats.get('type', 'Unknown')}")
            sections.append(f"Total Requests: {service_stats.get('total_requests', 0)}")
            sections.append(f"Errors: {service_stats.get('error_count', 0)}, Faults: {service_stats.get('fault_count', 0)}")
            sections.append(f"Avg Response Time: {service_stats.get('avg_response_time_ms', 0)}ms")
            sections.append(f"P99 Latency: {service_stats.get('p99_latency_ms', 0)}ms")
        
        if error_traces:
            sections.append(f"\nError Traces ({len(error_traces)}):")
            for t in error_traces[:3]:
                trace_id = t.get('trace_id', '')[:20]
                duration = t.get('duration_ms', 0)
                http_status = t.get('http_status', 0)
                sections.append(f"  - {trace_id}: {duration}ms, HTTP {http_status}")
        
        if slow_traces:
            sections.append(f"\nSlow Traces >1s ({len(slow_traces)}):")
            for t in slow_traces[:3]:
                trace_id = t.get('trace_id', '')[:20]
                response_time = t.get('response_time_ms', 0)
                sections.append(f"  - {trace_id}: {response_time}ms")
        
        if not error_traces and not slow_traces and not service_stats:
            sections.append("No X-Ray trace data found for this service.")
    else:
        sections.append("Tool call failed.")

    # Section 6: AWS Config / Configuration State
    sections.append("\n[Source: AWS Config]")
    config = tool_results.get('config')
    if config:
        summary = config.get('summary', {})
        non_compliant = config.get('non_compliant_resources', [])
        recent_changes = config.get('recent_changes', [])
        config_state = config.get('configuration_state', [])
        data_source = config.get('data_source', 'AWS Config')
        
        if summary.get('config_enabled'):
            sections.append("AWS Config: Enabled")
            sections.append(f"Non-compliant: {summary.get('total_non_compliant', 0)} | Changes: {summary.get('total_changes', 0)}")
            
            if non_compliant:
                sections.append("Non-compliant Resources:")
                for r in non_compliant[:3]:
                    sections.append(f"  - {r.get('resource_type', '')}: {r.get('resource_id', '')}")
            
            if recent_changes:
                sections.append("Recent Changes:")
                for c in recent_changes[:3]:
                    sections.append(f"  - {c.get('resource_type', '')}: {c.get('resource_id', '')} ({c.get('status', '')})")
        else:
            # Show Lambda configuration in a compact format
            sections.append(f"Source: {data_source}")
            if config_state:
                # Format as a compact table
                config_line = " | ".join([f"{item.get('setting')}: {item.get('value')} [{item.get('status')}]" for item in config_state[:4]])
                sections.append(f"Config: {config_line}")
                if len(config_state) > 4:
                    config_line2 = " | ".join([f"{item.get('setting')}: {item.get('value')} [{item.get('status')}]" for item in config_state[4:]])
                    sections.append(f"        {config_line2}")
                
                # Add summary metrics if available
                if summary.get('memory_mb'):
                    sections.append(f"Lambda: {summary.get('memory_mb')}MB memory, {summary.get('timeout_sec')}s timeout, {summary.get('runtime')}")
            else:
                sections.append("No configuration data available.")
    else:
        sections.append("Tool call failed.")

    # Summary section
    sections.append("\n[Investigation Summary]")
    sections.append(f"Service: {service}")
    sections.append(f"Alarm: {alarm_name}")
    sections.append(f"Suspected Root Cause: {root_cause}")
    
    # Add key findings
    findings = []
    if tool_results.get('deployments'):
        deps = tool_results['deployments']
        if deps.get('total_deployments', 0) > 0 or deps.get('total_config_changes', 0) > 0:
            findings.append(f"Recent changes detected: {deps.get('total_deployments', 0)} deployments, {deps.get('total_config_changes', 0)} config changes")
    
    if tool_results.get('xray'):
        xray = tool_results['xray']
        stats = xray.get('service_stats', {})
        if stats.get('error_count', 0) > 0 or stats.get('fault_count', 0) > 0:
            findings.append(f"X-Ray errors: {stats.get('error_count', 0)} errors, {stats.get('fault_count', 0)} faults")
    
    if tool_results.get('config'):
        cfg = tool_results['config']
        if cfg.get('summary', {}).get('total_non_compliant', 0) > 0:
            findings.append(f"Config compliance issues: {cfg['summary']['total_non_compliant']} non-compliant resources")
    
    if findings:
        sections.append("\nKey Findings:")
        for f in findings:
            sections.append(f"  * {f}")

    return "\n".join(sections)
'''

buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
buf.seek(0)

print("Updating agent-invoker Lambda to DIRECTLY call all 6 tools...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-invoker-dev', ZipFile=buf.read())
print(f"Done! Last modified: {r['LastModified']}")

# Add environment variable for agent-actions Lambda
import time
time.sleep(3)

print("\nAdding AGENT_ACTIONS_LAMBDA environment variable...")
try:
    config = lambda_client.get_function_configuration(FunctionName='outageshield-agent-invoker-dev')
    env_vars = config.get('Environment', {}).get('Variables', {})
    env_vars['AGENT_ACTIONS_LAMBDA'] = 'outageshield-agent-actions-dev'
    lambda_client.update_function_configuration(
        FunctionName='outageshield-agent-invoker-dev',
        Environment={'Variables': env_vars}
    )
    print("Environment variable added!")
except Exception as e:
    print(f"Note: {e}")

print("\n" + "=" * 60)
print("AGENT INVOKER - DIRECT TOOL CALLS")
print("=" * 60)
print("The agent-invoker now DIRECTLY calls all 6 tools:")
print("  1. searchIncidentHistory - Past incidents")
print("  2. searchLogs - OpenSearch logs")
print("  3. getRunbook - Remediation runbooks")
print("  4. checkDeployments - Deployment history")
print("  5. searchTraces - X-Ray traces")
print("  6. checkConfigDrift - AWS Config")
print()
print("This GUARANTEES all tools are called every time.")
