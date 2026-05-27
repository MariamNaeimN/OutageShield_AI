"""Check table counts and understand why 200 events."""
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Check events table
events_table = dynamodb.Table('outageshield-events-dev')
events_count = events_table.scan(Select='COUNT')['Count']

# Check incidents table  
incidents_table = dynamodb.Table('outageshield-incidents-dev')
incidents_count = incidents_table.scan(Select='COUNT')['Count']

print('Table Counts:')
print(f'  Events: {events_count}')
print(f'  Incidents: {incidents_count}')

# Sample events
print('\nSample Events (first 15):')
scan = events_table.scan(Limit=15)
for item in scan.get('Items', []):
    event_id = item.get('event_id', 'N/A')
    service = item.get('service', 'N/A')
    alarm = item.get('alarm_name', 'N/A')
    print(f'  {event_id}: {service} - {alarm}')

# Sample incidents
print('\nSample Incidents (first 15):')
scan = incidents_table.scan(Limit=15)
for item in scan.get('Items', []):
    inc_id = item.get('incident_id', 'N/A')
    service = item.get('service', 'N/A')
    alarm = item.get('alarm_name', 'N/A')
    print(f'  {inc_id}: {service} - {alarm}')
