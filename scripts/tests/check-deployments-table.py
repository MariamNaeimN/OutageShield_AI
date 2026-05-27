"""Check deployments table and add sample data."""
import boto3
from datetime import datetime, timedelta
import uuid

ddb = boto3.resource('dynamodb', region_name='us-east-1')
table = ddb.Table('outageshield-deployments-dev')

print('=' * 80)
print('DEPLOYMENTS TABLE CHECK')
print('=' * 80)

# Check existing data
response = table.scan(Limit=20)
items = response.get('Items', [])

print(f'\nExisting deployments: {len(items)}')
print()

services_found = set()
for item in items:
    service = item.get('service', 'N/A')
    services_found.add(service)
    print(f'Service: {service}')
    print(f'  ID: {item.get("deployment_id", "N/A")}')
    print(f'  Time: {item.get("timestamp", "N/A")}')
    print(f'  Status: {item.get("status", "N/A")}')
    print()

print(f'Services with deployments: {services_found}')

# Add sample deployments for test services
print('\n' + '=' * 80)
print('ADDING SAMPLE DEPLOYMENTS')
print('=' * 80)

test_services = ['payment-service', 'checkout-api', 'inventory-service', 'user-auth', 'order-processor']

for service in test_services:
    # Add a recent deployment (within last 2 hours)
    deployment_id = f'deploy-{service[:10]}-{str(uuid.uuid4())[:8]}'
    timestamp = (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z'
    
    item = {
        'deployment_id': deployment_id,
        'service': service,
        'timestamp': timestamp,
        'type': 'deployment',
        'version': '2.5.1',
        'previous_version': '2.5.0',
        'status': 'succeeded',
        'changes': f'Updated {service} with performance improvements and bug fixes',
        'commit_sha': str(uuid.uuid4())[:7],
        'deployed_by': 'jenkins-ci',
        'pipeline': f'{service}-pipeline',
        'environment': 'production'
    }
    
    try:
        table.put_item(Item=item)
        print(f'✓ Added deployment for {service}: {deployment_id}')
    except Exception as e:
        print(f'✗ Failed for {service}: {e}')

    # Add a config change (within last 1 hour)
    config_id = f'config-{service[:10]}-{str(uuid.uuid4())[:8]}'
    config_timestamp = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
    
    config_item = {
        'deployment_id': config_id,
        'service': service,
        'timestamp': config_timestamp,
        'type': 'config_change',
        'parameter': 'max_connections',
        'old_value': '50',
        'new_value': '100',
        'changed_by': 'terraform',
        'source': 'aws-config',
        'reason': 'Scaling for increased traffic'
    }
    
    try:
        table.put_item(Item=config_item)
        print(f'✓ Added config change for {service}: {config_id}')
    except Exception as e:
        print(f'✗ Failed config for {service}: {e}')

print('\n✅ Sample deployments added!')
print('Now the checkDeployments tool will find recent deployments for these services.')
