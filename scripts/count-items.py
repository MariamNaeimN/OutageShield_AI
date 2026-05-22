import boto3
d = boto3.resource('dynamodb', region_name='us-east-1')
for t in ['outageshield-incidents-dev', 'outageshield-events-dev', 'outageshield-workflow-state-dev', 'outageshield-postmortems-dev', 'outageshield-runbooks-dev']:
    count = d.Table(t).scan(Select='COUNT')['Count']
    print(f"  {t}: {count} items")
