"""
Update Bedrock Agent OpenAPI schema to include X-Ray and Config tools.
This adds 2 new endpoints to the agent's action group.
"""
import boto3
import json

bedrock_agent = boto3.client('bedrock-agent', region_name='us-east-1')

# New OpenAPI schema with 6 tools (4 original + X-Ray + Config)
OPENAPI_SCHEMA = {
    "openapi": "3.0.0",
    "info": {
        "title": "OutageShield Investigation Tools",
        "version": "2.0.0",
        "description": "Tools for autonomous incident investigation including logs, traces, config, and history"
    },
    "paths": {
        "/search-incidents": {
            "get": {
                "operationId": "searchIncidentHistory",
                "description": "Search past incidents for a service to find patterns and similar issues",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name to search incidents for"
                    }
                ],
                "responses": {
                    "200": {"description": "List of past incidents"}
                }
            }
        },
        "/search-logs": {
            "get": {
                "operationId": "searchLogs",
                "description": "Search OpenSearch logs for error patterns and anomalies related to the incident",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name to search logs for"
                    },
                    {
                        "name": "time_range",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Time range to search such as 1h or 6h or 24h"
                    }
                ],
                "responses": {
                    "200": {"description": "Log entries and patterns found"}
                }
            }
        },
        "/get-runbook": {
            "get": {
                "operationId": "getRunbook",
                "description": "Look up the remediation runbook for a specific service and alarm type",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name"
                    },
                    {
                        "name": "alarm_type",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Type of alarm such as HighLatency or High5xxRate or HighCPU"
                    }
                ],
                "responses": {
                    "200": {"description": "Runbook with remediation steps"}
                }
            }
        },
        "/check-deployments": {
            "get": {
                "operationId": "checkDeployments",
                "description": "Check recent deployments and configuration changes for a service that may have caused the incident",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name to check deployments for"
                    }
                ],
                "responses": {
                    "200": {"description": "Recent deployments and config changes"}
                }
            }
        },
        "/search-traces": {
            "get": {
                "operationId": "searchTraces",
                "description": "Search AWS X-Ray traces for latency issues, errors, and dependency problems related to the service",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name to search traces for"
                    },
                    {
                        "name": "time_range",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Time range to search such as 1h or 6h"
                    }
                ],
                "responses": {
                    "200": {"description": "X-Ray traces including errors, slow requests, and service graph"}
                }
            }
        },
        "/check-config-drift": {
            "get": {
                "operationId": "checkConfigDrift",
                "description": "Check AWS Config for compliance issues and configuration drift that may have caused the incident",
                "parameters": [
                    {
                        "name": "service",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Service name to check config compliance for"
                    }
                ],
                "responses": {
                    "200": {"description": "Non-compliant resources and recent configuration changes"}
                }
            }
        }
    }
}

# Updated agent instruction with new tools
AGENT_INSTRUCTION = """You are an expert Site Reliability Engineer (SRE) investigating cloud infrastructure incidents.
Your job is to autonomously investigate incidents by using ALL available tools:

1. searchIncidentHistory - Find similar past incidents on the same service
2. searchLogs - Query OpenSearch logs for error patterns and anomalies
3. getRunbook - Look up known remediation procedures
4. checkDeployments - Analyze deployment history for recent changes
5. searchTraces - Query X-Ray for latency issues and error traces (NEW)
6. checkConfigDrift - Check AWS Config for compliance issues (NEW)

When investigating an incident, you MUST:
- Call ALL 6 tools to gather comprehensive evidence
- Start with searchIncidentHistory and searchLogs
- Check searchTraces for latency/error patterns
- Check checkConfigDrift for compliance issues
- Cross-reference with checkDeployments and getRunbook

CRITICAL RULE — SOURCE ATTRIBUTION:
For EVERY finding you report, you MUST state which data source provided the information using these EXACT labels:
- [Source: Incident History DB] — for past incident findings
- [Source: OpenSearch Logs] — for log patterns and alarm data
- [Source: Runbook DB] — for runbook steps and procedures
- [Source: Deployment History] — for deployment and config change findings
- [Source: X-Ray Traces] — for latency, error traces, and service graph (NEW)
- [Source: AWS Config] — for compliance issues and configuration drift (NEW)

Do NOT present information without citing its source.
If a data source returned empty results, say "No data found from [source label]".

Always provide structured output with ALL sections:
- investigation_summary: What you found (with sources cited)
- similar_incidents: Past incidents [Source: Incident History DB]
- log_findings: Log patterns [Source: OpenSearch Logs]
- trace_findings: X-Ray traces [Source: X-Ray Traces]
- config_findings: Compliance issues [Source: AWS Config]
- deployment_correlation: Recent changes [Source: Deployment History]
- runbook_findings: Runbook steps [Source: Runbook DB]
"""

print("=" * 60)
print("Updating Bedrock Agent Schema with X-Ray and Config Tools")
print("=" * 60)
print()

# Get current agent
try:
    # List agents to find ours
    agents = bedrock_agent.list_agents()
    agent_id = None
    
    for agent in agents.get('agentSummaries', []):
        if 'outageshield' in agent.get('agentName', '').lower():
            agent_id = agent['agentId']
            print(f"Found agent: {agent['agentName']} ({agent_id})")
            break
    
    if not agent_id:
        print("ERROR: OutageShield agent not found!")
        print("Available agents:")
        for agent in agents.get('agentSummaries', []):
            print(f"  - {agent['agentName']} ({agent['agentId']})")
        exit(1)
    
    # Get agent details
    agent_details = bedrock_agent.get_agent(agentId=agent_id)
    agent = agent_details['agent']
    print(f"Agent status: {agent['agentStatus']}")
    
    # Update agent instruction
    print()
    print("Updating agent instruction...")
    bedrock_agent.update_agent(
        agentId=agent_id,
        agentName=agent['agentName'],
        agentResourceRoleArn=agent['agentResourceRoleArn'],
        foundationModel=agent['foundationModel'],
        instruction=AGENT_INSTRUCTION
    )
    print("✓ Agent instruction updated")
    
    # Get action groups
    action_groups = bedrock_agent.list_agent_action_groups(
        agentId=agent_id,
        agentVersion='DRAFT'
    )
    
    action_group_id = None
    for ag in action_groups.get('actionGroupSummaries', []):
        if 'investigation' in ag.get('actionGroupName', '').lower():
            action_group_id = ag['actionGroupId']
            print(f"Found action group: {ag['actionGroupName']} ({action_group_id})")
            break
    
    if action_group_id:
        # Get current action group details to preserve Lambda ARN
        ag_details = bedrock_agent.get_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupId=action_group_id
        )
        lambda_arn = ag_details['agentActionGroup']['actionGroupExecutor']['lambda']
        print(f"Lambda ARN: {lambda_arn}")
        
        # Update action group with new schema
        print()
        print("Updating action group schema...")
        bedrock_agent.update_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupId=action_group_id,
            actionGroupName='IncidentInvestigationTools',
            description='Tools for searching incidents, logs, traces, config, runbooks, and deployments',
            actionGroupExecutor={
                'lambda': lambda_arn
            },
            apiSchema={
                'payload': json.dumps(OPENAPI_SCHEMA)
            }
        )
        print("✓ Action group schema updated")
    
    # Prepare agent
    print()
    print("Preparing agent for deployment...")
    bedrock_agent.prepare_agent(agentId=agent_id)
    print("✓ Agent prepared")
    
    print()
    print("=" * 60)
    print("SUCCESS! Agent updated with 6 tools:")
    print("=" * 60)
    print("  1. searchIncidentHistory - Past incidents")
    print("  2. searchLogs - OpenSearch logs")
    print("  3. getRunbook - Remediation runbooks")
    print("  4. checkDeployments - Deployment history")
    print("  5. searchTraces - X-Ray traces (NEW)")
    print("  6. checkConfigDrift - AWS Config (NEW)")
    print()
    print("The agent will now use all 6 tools during investigation.")
    print("New source labels: [Source: X-Ray Traces], [Source: AWS Config]")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
