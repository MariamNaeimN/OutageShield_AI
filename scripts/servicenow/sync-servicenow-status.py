"""
Sync ServiceNow change request status fields with DynamoDB incidents.
Updates u_outageshield_status and u_outageshield_approval_status for all incidents
that have a ServiceNow change request.

Usage:
  python scripts/servicenow/sync-servicenow-status.py              # Sync all
  python scripts/servicenow/sync-servicenow-status.py INC-123      # Sync specific incident
"""

import boto3
import json
import base64
import urllib.request
import urllib.error
import sys

ssm = boto3.client('ssm', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Get ServiceNow credentials
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()

def make_request(endpoint, method='GET', data=None):
    url = f"https://{sn_instance}{endpoint}"
    if data:
        data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_approval_status(dynamo_status):
    """Map DynamoDB status to approval status"""
    status_lower = (dynamo_status or '').lower()
    if 'approved' in status_lower or 'mitigat' in status_lower or 'resolved' in status_lower:
        return 'APPROVED'
    elif 'rejected' in status_lower:
        return 'REJECTED'
    else:
        return 'PENDING'

def sync_incident(incident_id):
    """Sync a single incident's ServiceNow change request"""
    table = dynamodb.Table('outageshield-incidents-dev')
    resp = table.get_item(Key={'incident_id': incident_id})
    item = resp.get('Item')
    
    if not item:
        print(f"❌ Incident {incident_id} not found in DynamoDB")
        return False
    
    chg = item.get('servicenow_change', '')
    if not chg:
        print(f"⚠️  {incident_id}: No ServiceNow change request")
        return False
    
    service = item.get('service', 'unknown')
    severity = item.get('severity_score', '3')
    status = item.get('status', 'Awaiting Approval')
    approval_status = get_approval_status(status)
    
    # Get the change request sys_id
    result = make_request(f"/api/now/table/change_request?sysparm_query=number={chg}&sysparm_limit=1")
    if not result or not result.get('result'):
        print(f"❌ {incident_id}: Change {chg} not found in ServiceNow")
        return False
    
    sys_id = result['result'][0]['sys_id']
    current_sn_status = result['result'][0].get('u_outageshield_status', '')
    current_approval = result['result'][0].get('u_outageshield_approval_status', '')
    
    # Update the change request
    update_data = {
        'u_outageshield_incident_id': incident_id,
        'u_outageshield_service': service,
        'u_outageshield_severity': str(severity),
        'u_outageshield_status': status,
        'u_outageshield_approval_status': approval_status
    }
    
    update_result = make_request(f"/api/now/table/change_request/{sys_id}", method='PATCH', data=update_data)
    if update_result:
        print(f"✅ {incident_id} ({chg}): status='{status}', approval='{approval_status}'")
        if current_sn_status != status or current_approval != approval_status:
            print(f"   Changed from: status='{current_sn_status}', approval='{current_approval}'")
        return True
    else:
        print(f"❌ {incident_id}: Failed to update {chg}")
        return False

def sync_all_incidents():
    """Sync all incidents that have ServiceNow change requests"""
    table = dynamodb.Table('outageshield-incidents-dev')
    
    # Scan for all incidents with servicenow_change
    result = table.scan(
        FilterExpression='attribute_exists(servicenow_change) AND servicenow_change <> :empty',
        ExpressionAttributeValues={':empty': ''}
    )
    items = result.get('Items', [])
    
    while 'LastEvaluatedKey' in result:
        result = table.scan(
            FilterExpression='attribute_exists(servicenow_change) AND servicenow_change <> :empty',
            ExpressionAttributeValues={':empty': ''},
            ExclusiveStartKey=result['LastEvaluatedKey']
        )
        items.extend(result.get('Items', []))
    
    print(f"Found {len(items)} incidents with ServiceNow change requests\n")
    
    success = 0
    failed = 0
    for item in items:
        if sync_incident(item['incident_id']):
            success += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Synced: {success}, Failed: {failed}")
    return success, failed

if __name__ == '__main__':
    print("=" * 60)
    print("SYNC SERVICENOW STATUS FIELDS")
    print("=" * 60)
    print(f"ServiceNow Instance: {sn_instance}\n")
    
    if len(sys.argv) > 1:
        # Sync specific incidents
        for inc_id in sys.argv[1:]:
            sync_incident(inc_id)
    else:
        # Sync all
        sync_all_incidents()
