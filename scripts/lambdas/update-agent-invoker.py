"""Update agent-invoker Lambda to use Bedrock Agent with TOOL-ONLY output.
Extracts raw tool results from the agent trace - NO LLM interpretation = NO hallucination.
Now supports 6 tools: 4 original + X-Ray + Config."""
import boto3, zipfile, io

lambda_client = boto3.client('lambda', region_name='us-east-1')

code = r'''import json
import boto3
import os
import uuid

bedrock_agent = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')

AGENT_ID = os.environ.get('AGENT_ID', '')
AGENT_ALIAS_ID = os.environ.get('AGENT_ALIAS_ID', 'TSTALIASID')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')

def lambda_handler(event, context):
    """
    Invoke Bedrock Agent to call 6 tools, but ONLY use the raw tool results.
    We ignore the agent's text response entirely to prevent hallucination.
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
    if alarm_type.startswith('Outage signal'):
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

    prompt = f"""Execute ALL 6 tools in order for service '{service}':
1. searchIncidentHistory(service="{service}")
2. searchLogs(service="{service}", time_range="6h")
3. getRunbook(service="{service}", alarm_type="{alarm_type}")
4. checkDeployments(service="{service}")
5. searchTraces(service="{service}", time_range="1h")
6. checkConfigDrift(service="{service}")

Context: Alarm={alarm_name}, Root cause={root_cause}

IMPORTANT: Call all 6 tools. Do not skip any."""

    print(f"Invoking Bedrock Agent for {incident_id}: service={service}, alarm_type={alarm_type}")

    tool_results = {
        'incident_history': None,
        'logs': None,
        'runbook': None,
        'deployments': None,
        'xray': None,
        'config': None
    }

    try:
        response = bedrock_agent.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=str(uuid.uuid4()),
            inputText=prompt,
            enableTrace=True
        )

        # Process the event stream and extract ONLY tool results
        for event_stream in response.get('completion', []):
            # Extract tool invocation results from trace
            if 'trace' in event_stream:
                trace = event_stream['trace'].get('trace', {})
                orchestration = trace.get('orchestrationTrace', {})
                
                # Check for tool invocation output
                if 'observation' in orchestration:
                    obs = orchestration['observation']
                    if 'actionGroupInvocationOutput' in obs:
                        output = obs['actionGroupInvocationOutput']
                        text = output.get('text', '')
                        
                        # Parse the tool result
                        try:
                            result = json.loads(text) if text.startswith('{') else {'raw': text}
                        except:
                            result = {'raw': text}
                        
                        # Identify which tool this is from based on content
                        result_str = str(result).lower()
                        if 'total_past_incidents' in result_str or ('incidents' in result and 'total_past' in result_str):
                            tool_results['incident_history'] = result
                            print(f"Got incident history: {len(str(result))} chars")
                        elif 'error_traces' in result_str or 'slow_traces' in result_str or 'service_stats' in result_str:
                            tool_results['xray'] = result
                            print(f"Got X-Ray traces: {len(str(result))} chars")
                        elif 'non_compliant' in result_str or 'config_enabled' in result_str or 'compliance' in result_str:
                            tool_results['config'] = result
                            print(f"Got Config drift: {len(str(result))} chars")
                        elif 'patterns' in result or 'data_source' in result:
                            tool_results['logs'] = result
                            print(f"Got logs: {len(str(result))} chars")
                        elif 'runbook' in result or 'steps' in result_str:
                            tool_results['runbook'] = result
                            print(f"Got runbook: {len(str(result))} chars")
                        elif 'deployments' in result or 'config_changes' in result:
                            tool_results['deployments'] = result
                            print(f"Got deployments: {len(str(result))} chars")

        # Format investigation from RAW tool results only - NO LLM text
        investigation = format_tool_results(tool_results)
        print(f"Investigation formatted for {incident_id}: {len(investigation)} chars")

        table = dynamodb.Table(INCIDENTS_TABLE)
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET agent_investigation = :ai',
            ExpressionAttributeValues={':ai': investigation[:4000]}
        )

        return {
            'statusCode': 200,
            'incident_id': incident_id,
            'investigation': investigation[:4000],
            'status': 'completed',
            'tools_called': sum(1 for v in tool_results.values() if v is not None)
        }

    except Exception as e:
        print(f"Agent invocation failed: {e}")
        return {
            'statusCode': 200,
            'incident_id': incident_id,
            'investigation': f'Agent investigation failed: {str(e)[:100]}',
            'status': 'failed'
        }


def format_tool_results(tool_results):
    """Format investigation from RAW tool results ONLY - no LLM interpretation."""
    sections = []

    # Section 1: Incident History
    sections.append("[Source: Incident History DB]")
    ih = tool_results.get('incident_history')
    if ih:
        incidents = ih.get('incidents', [])
        if incidents:
            for inc in incidents[:5]:
                inc_id = inc.get('incident_id', 'Unknown')
                title = inc.get('title', 'No title')
                rc = inc.get('root_cause', 'Unknown')
                status = inc.get('status', 'Unknown')
                sections.append(f"- {inc_id}: {title} (Root cause: {rc}, Status: {status})")
        else:
            sections.append("No past incidents found for this service.")
    else:
        sections.append("Tool not called or no data returned.")

    # Section 2: OpenSearch Logs
    sections.append("\n[Source: OpenSearch Logs]")
    logs = tool_results.get('logs')
    if logs:
        patterns = logs.get('patterns', [])
        if patterns:
            for log in patterns[:5]:
                alarm = log.get('alarm_name', 'Unknown')
                msg = log.get('message', '')[:100]
                ts = log.get('timestamp', '')
                sections.append(f"- {alarm}: {msg} ({ts})")
        else:
            data_source = logs.get('data_source', 'Unknown')
            sections.append(f"No log entries found. Data source: {data_source}")
    else:
        sections.append("Tool not called or no data returned.")

    # Section 3: Runbook
    sections.append("\n[Source: Runbook DB]")
    rb_result = tool_results.get('runbook')
    if rb_result:
        if rb_result.get('found') and rb_result.get('runbook'):
            rb = rb_result['runbook']
            sections.append(f"Runbook: {rb.get('title', 'Unknown')}")
            sections.append(f"Category: {rb.get('category', 'Unknown')}, Estimated TTR: {rb.get('estimated_ttr', 'Unknown')}")
            steps = rb.get('steps', [])
            if steps:
                sections.append("Steps:")
                for i, step in enumerate(steps[:5], 1):
                    sections.append(f"  {i}. {step}")
        else:
            alarm_type = rb_result.get('alarm_type', 'Unknown')
            sections.append(f"No runbook found for alarm type: {alarm_type}")
    else:
        sections.append("Tool not called or no data returned.")

    # Section 4: Deployment History
    sections.append("\n[Source: Deployment History]")
    deps = tool_results.get('deployments')
    if deps:
        deployments = deps.get('deployments', [])
        config_changes = deps.get('config_changes', [])
        if deployments or config_changes:
            for dep in deployments[:3]:
                dep_id = dep.get('deployment_id', 'Unknown')
                version = dep.get('version', 'Unknown')
                status = dep.get('status', 'Unknown')
                changes = dep.get('changes', '')[:50]
                sections.append(f"- Deploy {dep_id}: v{version} ({status}) - {changes}")
            for cfg in config_changes[:3]:
                param = cfg.get('parameter', 'Unknown')
                old_val = cfg.get('old_value', '')
                new_val = cfg.get('new_value', '')
                sections.append(f"- Config: {param} changed from {old_val} to {new_val}")
        else:
            sections.append("No recent deployments or config changes found.")
    else:
        sections.append("Tool not called or no data returned.")

    # Section 5: X-Ray Traces
    sections.append("\n[Source: X-Ray Traces]")
    xray = tool_results.get('xray')
    if xray:
        error_traces = xray.get('error_traces', [])
        slow_traces = xray.get('slow_traces', [])
        service_stats = xray.get('service_stats', {})
        insights = xray.get('insights', [])
        
        if service_stats:
            sections.append(f"Service: {service_stats.get('name', 'Unknown')}, Type: {service_stats.get('type', 'Unknown')}")
            sections.append(f"Requests: {service_stats.get('total_requests', 0)}, Errors: {service_stats.get('error_count', 0)}, Faults: {service_stats.get('fault_count', 0)}")
            sections.append(f"Avg Response Time: {service_stats.get('avg_response_time_ms', 0)}ms")
        
        if error_traces:
            sections.append("Error Traces:")
            for t in error_traces[:3]:
                sections.append(f"  - {t.get('trace_id', '')[:20]}: {t.get('duration_ms', 0)}ms, HTTP {t.get('http_status', 0)}")
        
        if slow_traces:
            sections.append("Slow Traces (>1s):")
            for t in slow_traces[:3]:
                sections.append(f"  - {t.get('trace_id', '')[:20]}: {t.get('response_time_ms', 0)}ms")
        
        if insights:
            sections.append("X-Ray Insights:")
            for i in insights[:2]:
                sections.append(f"  - {i.get('category', 'Unknown')}: {i.get('summary', '')[:80]}")
        
        if not error_traces and not slow_traces and not service_stats:
            sections.append("No X-Ray trace data found for this service.")
    else:
        sections.append("Tool not called or no data returned.")

    # Section 6: AWS Config
    sections.append("\n[Source: AWS Config]")
    config = tool_results.get('config')
    if config:
        summary = config.get('summary', {})
        non_compliant = config.get('non_compliant_resources', [])
        recent_changes = config.get('recent_changes', [])
        
        if summary.get('config_enabled'):
            sections.append(f"Config enabled: Yes, Non-compliant resources: {summary.get('total_non_compliant', 0)}, Recent changes: {summary.get('total_changes', 0)}")
        else:
            sections.append("AWS Config is not enabled in this region.")
        
        if non_compliant:
            sections.append("Non-compliant Resources:")
            for r in non_compliant[:3]:
                sections.append(f"  - {r.get('resource_type', '')}: {r.get('resource_id', '')}")
                for v in r.get('violations', [])[:2]:
                    sections.append(f"    Rule: {v.get('rule_name', '')}")
        
        if recent_changes:
            sections.append("Recent Config Changes:")
            for c in recent_changes[:3]:
                sections.append(f"  - {c.get('resource_type', '')}: {c.get('resource_id', '')} ({c.get('status', '')})")
        
        if not non_compliant and not recent_changes and summary.get('config_enabled'):
            sections.append("No compliance issues or recent changes found.")
    else:
        sections.append("Tool not called or no data returned.")

    return "\n".join(sections)
'''

buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', code)
buf.seek(0)

print("Updating agent-invoker Lambda to use Bedrock Agent with TOOL-ONLY output...")
r = lambda_client.update_function_code(FunctionName='outageshield-agent-invoker-dev', ZipFile=buf.read())
print(f"Done! Last modified: {r['LastModified']}")

print("\n=== BEDROCK AGENT + NO HALLUCINATION (6 TOOLS) ===")
print("The agent-invoker Lambda now:")
print("  1. Invokes Bedrock Agent with enableTrace=True")
print("  2. Agent calls all 6 tools:")
print("     - searchIncidentHistory")
print("     - searchLogs")
print("     - getRunbook")
print("     - checkDeployments")
print("     - searchTraces (X-Ray)")
print("     - checkConfigDrift (AWS Config)")
print("  3. Extracts RAW tool results from the trace (actionGroupInvocationOutput)")
print("  4. Formats output from tool results ONLY - ignores agent's text response")
print("\nBedrock Agent orchestrates tool calls, but output is ONLY from tools = NO hallucination!")
