"""Re-run remediation lambda for a specific incident."""
import boto3, json, sys

incident_id = sys.argv[1] if len(sys.argv) > 1 else 'INC-F3B26508'

lc = boto3.client('lambda', region_name='us-east-1')
db = boto3.resource('dynamodb', region_name='us-east-1')

table = db.Table('outageshield-incidents-dev')
item = table.get_item(Key={'incident_id': incident_id}).get('Item', {})

if not item:
    print(f'Incident {incident_id} not found')
    exit(1)

print(f'Service: {item.get("service")}')
print(f'Root cause: {str(item.get("root_cause", ""))[:80]}')

root_causes = json.loads(item.get('root_causes_raw', '[]'))
event = {
    'signal': {'signal_id': incident_id},
    'incident_context': {'service': item.get('service', 'unknown')},
    'root_causes': root_causes,
    'step3': {'root_causes': root_causes, 'incident_context_id': incident_id},
    'step3b': {'investigation': item.get('agent_investigation', '')}
}

print('Invoking remediation lambda...')
r = lc.invoke(
    FunctionName='outageshield-remediation-recommend-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps(event, default=str)
)
result = json.loads(r['Payload'].read().decode())
recs = result.get('recommendations', [])
print(f'\nResult: {len(recs)} recommendations')
for rec in recs:
    print(f'  [{rec.get("source","?")}] {rec.get("category","?")} conf={rec.get("confidence","?")}%')
print(f'\nSummary: {result.get("summary", "")}')
