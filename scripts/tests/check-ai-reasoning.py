"""Check AI reasoning table for an incident."""
import boto3
import json
import sys

ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-ai-reasoning-dev')

inc_id = sys.argv[1] if len(sys.argv) > 1 else 'INC-C7E7E6CF'

print(f"Checking AI reasoning table for: {inc_id}")
print("=" * 60)

from boto3.dynamodb.conditions import Key
resp = table.query(KeyConditionExpression=Key('incident_id').eq(inc_id))

items = resp.get('Items', [])
print(f"Items found: {len(items)}")

for item in items:
    print(f"\n📅 Created: {item.get('created_at')}")
    print(f"🔧 Service: {item.get('service')}")
    print(f"⚠️ Severity: {item.get('severity')}")
    print(f"🎯 Root Cause: {item.get('root_cause', '')[:100]}...")
    print(f"📊 Total Recommendations: {item.get('total_recommendations')}")
    print(f"\n🤖 AI Summary:")
    print("-" * 60)
    print(item.get('ai_summary', 'N/A'))
    print("-" * 60)
