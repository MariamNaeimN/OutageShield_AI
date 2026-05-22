"""Get a full sample incident to show the reasoning flow."""
import boto3
import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Get one incident with full data
table = dynamodb.Table('outageshield-incidents-dev')
response = table.scan(Limit=5)
items = response.get('Items', [])

# Find one with root_cause and recommendations
for item in items:
    if item.get('root_cause') and item.get('recommendations_raw'):
        print("=" * 70)
        print("  FULL INCIDENT RECORD")
        print("=" * 70)
        print(json.dumps(item, indent=2, cls=DecimalEncoder, default=str))
        break
else:
    if items:
        print(json.dumps(items[0], indent=2, cls=DecimalEncoder, default=str))
    else:
        print("No incidents found yet. Wait for workflows to complete.")
