import boto3
cf = boto3.client('cloudformation', region_name='us-east-1')
events = cf.describe_stack_events(StackName='outageshield-bedrock-agent-dev')['StackEvents']
for e in events:
    if e['ResourceStatus'] == 'CREATE_FAILED':
        print(f"{e['LogicalResourceId']}: {e.get('ResourceStatusReason', 'No reason')}")
