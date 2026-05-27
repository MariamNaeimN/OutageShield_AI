"""Check Bedrock Agent configuration and action group schema."""
import boto3
import json

bedrock_agent = boto3.client('bedrock-agent', region_name='us-east-1')

# List agents
agents = bedrock_agent.list_agents()
for agent in agents.get('agentSummaries', []):
    if 'outageshield' in agent.get('agentName', '').lower():
        agent_id = agent['agentId']
        print(f"Agent: {agent['agentName']} ({agent_id})")
        print(f"Status: {agent.get('agentStatus', 'N/A')}")
        
        # Get action groups
        action_groups = bedrock_agent.list_agent_action_groups(
            agentId=agent_id,
            agentVersion='DRAFT'
        )
        
        print()
        print('Action Groups:')
        for ag in action_groups.get('actionGroupSummaries', []):
            print(f"  - {ag['actionGroupName']} ({ag['actionGroupId']})")
            
            # Get action group details
            ag_details = bedrock_agent.get_agent_action_group(
                agentId=agent_id,
                agentVersion='DRAFT',
                actionGroupId=ag['actionGroupId']
            )
            
            schema = ag_details['agentActionGroup'].get('apiSchema', {})
            if 'payload' in schema:
                api_spec = json.loads(schema['payload'])
                paths = api_spec.get('paths', {})
                print(f"    Endpoints ({len(paths)}):")
                for path in paths:
                    print(f"      - {path}")
