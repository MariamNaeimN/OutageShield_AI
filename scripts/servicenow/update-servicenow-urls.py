"""
Update ServiceNow URLs in DynamoDB incidents to use the OutageShield UI Page
instead of the standard Change Request form.

Old format: https://dev252089.service-now.com/change_request.do?sysparm_query=number=CHG0030058
New format: https://dev252089.service-now.com/outageshield_incident.do?number=CHG0030058
"""
import boto3
import re

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')

# Get ServiceNow instance
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']

# Tables
INCIDENTS_TABLE = 'outageshield-incidents-dev'

def update_servicenow_urls():
    table = dynamodb.Table(INCIDENTS_TABLE)
    
    # Scan all incidents
    response = table.scan()
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    print(f"Found {len(items)} incidents")
    
    updated = 0
    for item in items:
        incident_id = item.get('incident_id')
        servicenow_change = item.get('servicenow_change', '')
        servicenow_url = item.get('servicenow_url', '')
        
        # Check if there's a ServiceNow change number
        if servicenow_change:
            # Extract CHG number if it's a URL
            chg_match = re.search(r'(CHG\d+)', str(servicenow_change))
            if chg_match:
                chg_number = chg_match.group(1)
            else:
                chg_number = servicenow_change
            
            # Create new UI Page URL
            new_url = f"https://{sn_instance}/outageshield_incident.do?number={chg_number}"
            
            # Update the incident
            update_expr = 'SET servicenow_url = :url'
            expr_values = {':url': new_url}
            
            # Also update servicenow_change if it was a URL
            if 'change_request.do' in str(servicenow_change):
                update_expr += ', servicenow_change = :chg'
                expr_values[':chg'] = chg_number
            
            table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
            
            print(f"  ✅ {incident_id}: {chg_number} -> {new_url}")
            updated += 1
        elif servicenow_url and 'change_request.do' in servicenow_url:
            # Extract CHG number from URL
            chg_match = re.search(r'(CHG\d+)', servicenow_url)
            if chg_match:
                chg_number = chg_match.group(1)
                new_url = f"https://{sn_instance}/outageshield_incident.do?number={chg_number}"
                
                table.update_item(
                    Key={'incident_id': incident_id},
                    UpdateExpression='SET servicenow_url = :url',
                    ExpressionAttributeValues={':url': new_url}
                )
                
                print(f"  ✅ {incident_id}: {chg_number} -> {new_url}")
                updated += 1
    
    print(f"\nUpdated {updated} incidents with new ServiceNow UI Page URLs")
    print(f"New URL format: https://{sn_instance}/outageshield_incident.do?number=CHGxxxxxxx")

if __name__ == '__main__':
    print("=" * 60)
    print("  UPDATE SERVICENOW URLS TO UI PAGE FORMAT")
    print("=" * 60)
    update_servicenow_urls()
