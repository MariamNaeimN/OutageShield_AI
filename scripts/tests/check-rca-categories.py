"""Check RCA categories in ALL incidents."""
import boto3
import json

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('outageshield-incidents-dev')

# Get ALL incidents
response = table.scan()
items = response.get('Items', [])

# Handle pagination
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response.get('Items', []))

print("=" * 70)
print(f"CHECKING RCA CATEGORIES IN ALL {len(items)} INCIDENTS")
print("=" * 70)

# Track category stats
category_counts = {}
missing_category = []
valid_categories = ['capacity', 'performance', 'configuration', 'deployment', 'dependency', 'unknown']

for item in items:
    incident_id = item.get('incident_id', 'N/A')
    raw = item.get('root_causes_raw', '[]')
    
    try:
        causes = json.loads(raw) if raw else []
        for i, c in enumerate(causes[:3]):
            cat = c.get('category', '')
            
            # Count categories
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1
            else:
                missing_category.append(f"{incident_id} - cause #{i+1}")
            
            # Check for invalid categories
            if cat and cat not in valid_categories:
                print(f"⚠️  {incident_id}: Invalid category '{cat}'")
                
    except Exception as e:
        print(f"❌ {incident_id}: Parse error - {e}")

print("\n" + "=" * 70)
print("CATEGORY DISTRIBUTION")
print("=" * 70)
for cat in sorted(category_counts.keys()):
    count = category_counts[cat]
    bar = "█" * (count // 2)
    print(f"  {cat:15} : {count:4} {bar}")

print(f"\n  TOTAL CAUSES   : {sum(category_counts.values())}")

if missing_category:
    print("\n" + "=" * 70)
    print(f"⚠️  MISSING CATEGORIES ({len(missing_category)})")
    print("=" * 70)
    for m in missing_category[:10]:
        print(f"  - {m}")
    if len(missing_category) > 10:
        print(f"  ... and {len(missing_category) - 10} more")
else:
    print("\n✅ ALL ROOT CAUSES HAVE VALID CATEGORIES!")

print("\n" + "=" * 70)
