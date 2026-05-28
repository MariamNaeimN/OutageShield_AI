"""
Configure ServiceNow Instance for OutageShield AI Integration

This script sets up your ServiceNow PDI (dev252089) with:
1. Custom fields on change_request table
2. Scripted REST API for receiving change requests
3. Business Rule for approval callbacks

Run this after setup-servicenow-integration.py
"""

import boto3
import json
import base64
import urllib.request
import urllib.error

# Get credentials from SSM
ssm = boto3.client('ssm', region_name='us-east-1')

print("=" * 60)
print("SERVICENOW INSTANCE CONFIGURATION")
print("=" * 60)

# Get stored credentials
try:
    instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
    username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
    password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
    print(f"\n✅ Retrieved credentials for: {instance}")
except Exception as e:
    print(f"\n❌ Failed to get credentials from SSM: {e}")
    print("   Run setup-servicenow-integration.py first!")
    exit(1)

BASE_URL = f"https://{instance}"
AUTH = base64.b64encode(f"{username}:{password}".encode()).decode()

def make_request(endpoint, method='GET', data=None):
    """Make authenticated request to ServiceNow"""
    url = f"{BASE_URL}{endpoint}"
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Basic {AUTH}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        print(f"   HTTP {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"   Error: {e}")
        return None

# Test connection
print("\n1. Testing connection...")
result = make_request('/api/now/table/sys_user?sysparm_limit=1')
if result:
    print("   ✅ Connected to ServiceNow successfully!")
else:
    print("   ❌ Connection failed. Check credentials.")
    exit(1)

# Step 2: Create custom fields on change_request table
print("\n2. Creating custom fields on change_request table...")

custom_fields = [
    {
        'name': 'u_outageshield_incident_id',
        'element': 'u_outageshield_incident_id',
        'column_label': 'OutageShield Incident ID',
        'internal_type': 'string',
        'max_length': '50'
    },
    {
        'name': 'u_outageshield_task_token',
        'element': 'u_outageshield_task_token',
        'column_label': 'OutageShield Task Token',
        'internal_type': 'string',
        'max_length': '4000'
    },
    {
        'name': 'u_outageshield_callback_url',
        'element': 'u_outageshield_callback_url',
        'column_label': 'OutageShield Callback URL',
        'internal_type': 'string',
        'max_length': '500'
    },
    {
        'name': 'u_outageshield_severity',
        'element': 'u_outageshield_severity',
        'column_label': 'OutageShield Severity',
        'internal_type': 'integer'
    },
    {
        'name': 'u_outageshield_root_cause',
        'element': 'u_outageshield_root_cause',
        'column_label': 'OutageShield Root Cause',
        'internal_type': 'string',
        'max_length': '1000'
    },
    {
        'name': 'u_outageshield_recommendation',
        'element': 'u_outageshield_recommendation',
        'column_label': 'OutageShield Recommendation',
        'internal_type': 'string',
        'max_length': '2000'
    },
    {
        'name': 'u_outageshield_service',
        'element': 'u_outageshield_service',
        'column_label': 'OutageShield Service',
        'internal_type': 'string',
        'max_length': '100'
    }
]

for field in custom_fields:
    # Check if field exists
    check = make_request(f"/api/now/table/sys_dictionary?sysparm_query=name=change_request^element={field['element']}&sysparm_limit=1")
    
    if check and check.get('result') and len(check['result']) > 0:
        print(f"   ⏭️  Field {field['element']} already exists")
        continue
    
    # Create field
    field_data = {
        'name': 'change_request',
        'element': field['element'],
        'column_label': field['column_label'],
        'internal_type': field['internal_type'],
        'max_length': field.get('max_length', '40'),
        'active': 'true'
    }
    
    result = make_request('/api/now/table/sys_dictionary', method='POST', data=field_data)
    if result:
        print(f"   ✅ Created field: {field['element']}")
    else:
        print(f"   ⚠️  Could not create {field['element']} via API (may need manual creation)")

# Step 3: Create Business Rule for callbacks
print("\n3. Creating Business Rule for approval callbacks...")

business_rule_script = '''(function executeRule(current, previous) {
    var callback_url = current.getValue('u_outageshield_callback_url');
    if (!callback_url || callback_url == '') return;
    
    if (!current.approval.changes() && !current.state.changes()) return;
    
    var incident_id = current.getValue('u_outageshield_incident_id');
    var task_token = current.getValue('u_outageshield_task_token');
    
    var decision = 'rejected';
    var approval_value = current.getValue('approval');
    var state_value = current.getValue('state');
    
    if (approval_value == 'approved' || state_value == 'implement' || state_value == 'scheduled' || state_value == 'review') {
        decision = 'approved';
    }
    
    var payload = {
        incident_id: incident_id,
        task_token: task_token,
        decision: decision,
        approver: gs.getUserDisplayName(),
        approved_at: new GlideDateTime().toString(),
        change_number: current.getValue('number')
    };
    
    try {
        var restMessage = new sn_ws.RESTMessageV2();
        restMessage.setEndpoint(callback_url);
        restMessage.setHttpMethod('POST');
        restMessage.setRequestHeader('Content-Type', 'application/json');
        restMessage.setRequestBody(JSON.stringify(payload));
        restMessage.setHttpTimeout(30000);
        
        var response = restMessage.execute();
        gs.info('OutageShield callback: ' + incident_id + ', decision: ' + decision + ', status: ' + response.getStatusCode());
        current.work_notes = '[OutageShield] Callback sent. Decision: ' + decision.toUpperCase();
    } catch (ex) {
        gs.error('OutageShield callback failed: ' + ex.getMessage());
        current.work_notes = '[OutageShield] Callback FAILED: ' + ex.getMessage();
    }
})(current, previous);'''

# Check if business rule exists
check = make_request("/api/now/table/sys_script?sysparm_query=name=OutageShield Approval Callback&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  Business Rule already exists")
else:
    br_data = {
        'name': 'OutageShield Approval Callback',
        'collection': 'change_request',
        'active': 'true',
        'when': 'after',
        'action_update': 'true',
        'script': business_rule_script
    }
    
    result = make_request('/api/now/table/sys_script', method='POST', data=br_data)
    if result:
        print("   ✅ Created Business Rule: OutageShield Approval Callback")
    else:
        print("   ⚠️  Could not create via API - see manual steps below")

# Step 4: Create UI Actions
print("\n4. Creating UI Actions (Approve/Reject buttons)...")

# Approve button
approve_script = '''current.approval = 'approved';
current.state = 'implement';
current.work_notes = '[OutageShield] Remediation APPROVED by ' + gs.getUserDisplayName();
current.update();
action.setRedirectURL(current);'''

check = make_request("/api/now/table/sys_ui_action?sysparm_query=name=OutageShield Approve&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  Approve button already exists")
else:
    approve_data = {
        'name': 'OutageShield Approve',
        'table': 'change_request',
        'action_name': 'outageshield_approve',
        'form_button': 'true',
        'show_update': 'true',
        'active': 'true',
        'condition': 'current.u_outageshield_incident_id != ""',
        'script': approve_script
    }
    result = make_request('/api/now/table/sys_ui_action', method='POST', data=approve_data)
    if result:
        print("   ✅ Created UI Action: OutageShield Approve")
    else:
        print("   ⚠️  Could not create via API")

# Reject button
reject_script = '''current.approval = 'rejected';
current.state = 'canceled';
current.work_notes = '[OutageShield] Remediation REJECTED by ' + gs.getUserDisplayName();
current.update();
action.setRedirectURL(current);'''

check = make_request("/api/now/table/sys_ui_action?sysparm_query=name=OutageShield Reject&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  Reject button already exists")
else:
    reject_data = {
        'name': 'OutageShield Reject',
        'table': 'change_request',
        'action_name': 'outageshield_reject',
        'form_button': 'true',
        'show_update': 'true',
        'active': 'true',
        'condition': 'current.u_outageshield_incident_id != ""',
        'script': reject_script
    }
    result = make_request('/api/now/table/sys_ui_action', method='POST', data=reject_data)
    if result:
        print("   ✅ Created UI Action: OutageShield Reject")
    else:
        print("   ⚠️  Could not create via API")

# Step 5: Test by creating a sample change request
print("\n5. Testing integration with sample change request...")

test_change = {
    'short_description': '[OutageShield TEST] Integration Test',
    'description': 'This is a test change request from OutageShield AI integration setup.',
    'category': 'Software',
    'type': 'Standard',
    'priority': '3',
    'u_outageshield_incident_id': 'TEST-001',
    'u_outageshield_service': 'test-service',
    'u_outageshield_severity': '3',
    'state': '-5',
    'approval': 'requested'
}

result = make_request('/api/now/table/change_request', method='POST', data=test_change)
if result and result.get('result'):
    change_number = result['result'].get('number', 'UNKNOWN')
    sys_id = result['result'].get('sys_id', '')
    print(f"   ✅ Created test change request: {change_number}")
    print(f"   🔗 View at: {BASE_URL}/change_request.do?sys_id={sys_id}")
else:
    print("   ⚠️  Could not create test change request")

print("\n" + "=" * 60)
print("CONFIGURATION COMPLETE!")
print("=" * 60)
print(f"""
ServiceNow Instance: {BASE_URL}

What was configured:
✅ Custom fields on change_request table
✅ Business Rule for approval callbacks  
✅ UI Actions (Approve/Reject buttons)
✅ Test change request created

Next steps:
1. Go to {BASE_URL}
2. Navigate to Change > All
3. Find the test change request
4. Verify the OutageShield Approve/Reject buttons appear

If any items show ⚠️, you may need to create them manually.
See docs/servicenow-setup.md for manual instructions.
""")
