import boto3, json
sfn = boto3.client('stepfunctions', region_name='us-east-1')

# Find the state machine
machines = sfn.list_state_machines(maxResults=10)['stateMachines']
sm_arn = None
for m in machines:
    if 'outageshield-workflow' in m['name']:
        sm_arn = m['stateMachineArn']
        break

if not sm_arn:
    print("No state machine found")
    exit()

print(f"State Machine: {sm_arn}")

# Check recent executions
execs = sfn.list_executions(stateMachineArn=sm_arn, maxResults=5)['executions']
print(f"\nRecent executions: {len(execs)}")
for ex in execs[:3]:
    print(f"  {ex['name'][:30]}... Status: {ex['status']}")
    if ex['status'] == 'FAILED':
        detail = sfn.describe_execution(executionArn=ex['executionArn'])
        print(f"    Error: {detail.get('error', 'N/A')}")
        print(f"    Cause: {detail.get('cause', 'N/A')[:200]}")
