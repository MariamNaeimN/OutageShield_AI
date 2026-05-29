"""
Create ServiceNow UI for OutageShield Incident Details
- Displays all data from DB
- Creates organized UX-friendly UI with URL links
- Adds Approve/Reject buttons for remediation workflow
"""

import boto3
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from decimal import Decimal
from datetime import datetime

ssm = boto3.client('ssm', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Get ServiceNow credentials
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

# OutageShield URLs
# CloudFront serves the static React dashboard
DASHBOARD_URL = "https://d2k1km1tzlio49.cloudfront.net"
# API Gateway serves the data endpoints
API_URL = "https://601lnlm7r5.execute-api.us-east-1.amazonaws.com/dev"

# DynamoDB Tables
INCIDENTS_TABLE = 'outageshield-incidents-dev'
POSTMORTEMS_TABLE = 'outageshield-postmortems-dev'

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        return super().default(obj)

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
        print(f"   HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"   Error: {e}")
        return None


# ============================================================
# DATABASE DISPLAY FUNCTIONS
# ============================================================

def get_all_incidents():
    table = dynamodb.Table(INCIDENTS_TABLE)
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items

def get_all_postmortems():
    table = dynamodb.Table(POSTMORTEMS_TABLE)
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items

def display_value(value, indent=0):
    prefix = "  " * indent
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            lines.append(f"{prefix}  {k}: {display_value(v, indent+1)}")
        return "\n" + "\n".join(lines) if lines else "{}"
    elif isinstance(value, list):
        if len(value) == 0:
            return "[]"
        if len(value) <= 3 and all(isinstance(v, (str, int, float, Decimal)) for v in value):
            return str(value)
        lines = []
        for item in value[:5]:
            lines.append(f"{prefix}  - {display_value(item, indent+1)}")
        if len(value) > 5:
            lines.append(f"{prefix}  ... and {len(value)-5} more")
        return "\n" + "\n".join(lines)
    elif isinstance(value, str) and len(value) > 150:
        return f"{value[:150]}... ({len(value)} chars)"
    else:
        return str(value)

def display_incident(incident, index):
    print(f"\n{'─' * 70}")
    print(f"  INCIDENT #{index + 1}")
    print(f"{'─' * 70}")
    priority_keys = ['incident_id', 'service', 'status', 'severity_score', 'business_impact_score',
                     'affected_users', 'revenue_at_risk', 'root_cause', 'servicenow_change',
                     'workflow_step', 'created_at', 'timestamp']
    shown_keys = set()
    for key in priority_keys:
        if key in incident:
            print(f"  {key}: {display_value(incident[key])}")
            shown_keys.add(key)
    print(f"\n  --- Additional Fields ---")
    for key in sorted(incident.keys()):
        if key not in shown_keys:
            print(f"  {key}: {display_value(incident[key])}")

def display_postmortem(pm, index):
    print(f"\n{'─' * 70}")
    print(f"  POSTMORTEM #{index + 1}")
    print(f"{'─' * 70}")
    priority_keys = ['postmortem_id', 'incident_id', 'service', 'created_at', 'summary']
    shown_keys = set()
    for key in priority_keys:
        if key in pm:
            print(f"  {key}: {display_value(pm[key])}")
            shown_keys.add(key)
    print(f"\n  --- Additional Fields ---")
    for key in sorted(pm.keys()):
        if key not in shown_keys:
            print(f"  {key}: {display_value(pm[key])}")


# ============================================================
# MAIN EXECUTION - DISPLAY ALL DATA
# ============================================================

print("=" * 70)
print("  OUTAGESHIELD - COMPLETE DATABASE DISPLAY")
print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

print("\n" + "=" * 70)
print("  TABLE: outageshield-incidents-dev")
print("=" * 70)

incidents = get_all_incidents()
print(f"\n  Total Incidents: {len(incidents)}")
all_incident_fields = set()
for inc in incidents:
    all_incident_fields.update(inc.keys())
print(f"  Fields: {', '.join(sorted(all_incident_fields))}")
for i, incident in enumerate(incidents):
    display_incident(incident, i)

print("\n" + "=" * 70)
print("  TABLE: outageshield-postmortems-dev")
print("=" * 70)

postmortems = get_all_postmortems()
print(f"\n  Total Postmortems: {len(postmortems)}")
all_pm_fields = set()
for pm in postmortems:
    all_pm_fields.update(pm.keys())
print(f"  Fields: {', '.join(sorted(all_pm_fields))}")
for i, pm in enumerate(postmortems):
    display_postmortem(pm, i)

print("\n" + "=" * 70)
print("  DATABASE SUMMARY")
print("=" * 70)
print(f"  Total Incidents: {len(incidents)}")
print(f"  Total Postmortems: {len(postmortems)}")
sn_incidents = [inc for inc in incidents if inc.get('servicenow_change')]
print(f"  Incidents with ServiceNow: {len(sn_incidents)}")

statuses = {}
for inc in incidents:
    status = inc.get('status', 'UNKNOWN')
    statuses[status] = statuses.get(status, 0) + 1
print(f"\n  By Status:")
for status, count in sorted(statuses.items()):
    print(f"    {status}: {count}")

services = {}
for inc in incidents:
    service = inc.get('service', 'UNKNOWN')
    services[service] = services.get(service, 0) + 1
print(f"\n  By Service:")
for service, count in sorted(services.items()):
    print(f"    {service}: {count}")


# ============================================================
# SERVICENOW UI CREATION
# ============================================================
print("\n" + "=" * 70)
print("  CREATING SERVICENOW UI")
print("=" * 70)

# Step 1: Create fields
print("\n1. Creating fields on change_request table...")

fields = [
    # Basic Info
    {'column_label': 'OutageShield Incident ID', 'element': 'u_outageshield_incident_id', 'internal_type': 'string', 'max_length': 100},
    {'column_label': 'OutageShield Service', 'element': 'u_outageshield_service', 'internal_type': 'string', 'max_length': 200},
    {'column_label': 'OutageShield Severity', 'element': 'u_outageshield_severity', 'internal_type': 'integer'},
    {'column_label': 'OutageShield Status', 'element': 'u_outageshield_status', 'internal_type': 'string', 'max_length': 50},
    {'column_label': 'OutageShield Approval Status', 'element': 'u_outageshield_approval_status', 'internal_type': 'string', 'max_length': 50},
    # URL Links
    {'column_label': 'Dashboard URL', 'element': 'u_outageshield_dashboard_url', 'internal_type': 'url'},
    {'column_label': 'Investigation URL', 'element': 'u_outageshield_investigation_url', 'internal_type': 'url'},
    {'column_label': 'Root Cause URL', 'element': 'u_outageshield_rca_url', 'internal_type': 'url'},
    {'column_label': 'Remediation URL', 'element': 'u_outageshield_remediation_url', 'internal_type': 'url'},
    {'column_label': 'Postmortem URL', 'element': 'u_outageshield_postmortem_url', 'internal_type': 'url'},
    {'column_label': 'Impact URL', 'element': 'u_outageshield_impact_url', 'internal_type': 'url'},
    {'column_label': 'Timeline URL', 'element': 'u_outageshield_timeline_url', 'internal_type': 'url'},
    {'column_label': 'Metrics URL', 'element': 'u_outageshield_metrics_url', 'internal_type': 'url'},
    # Approval URLs
    {'column_label': 'Approve URL', 'element': 'u_outageshield_approve_url', 'internal_type': 'url'},
    {'column_label': 'Reject URL', 'element': 'u_outageshield_reject_url', 'internal_type': 'url'},
]

for field in fields:
    field_data = {
        'name': 'change_request',
        'column_label': field['column_label'],
        'element': field['element'],
        'internal_type': field['internal_type'],
        'max_length': field.get('max_length', 40),
        'active': True
    }
    check = make_request(f"/api/now/table/sys_dictionary?sysparm_query=name=change_request^element={field['element']}&sysparm_limit=1")
    if check and check.get('result') and len(check['result']) > 0:
        print(f"   ⏭️  Exists: {field['element']}")
    else:
        result = make_request('/api/now/table/sys_dictionary', method='POST', data=field_data)
        if result:
            print(f"   ✅ Created: {field['element']}")


# Step 2: Create Form Sections
print("\n2. Creating Form Sections...")

sections = [
    {'name': 'OutageShield Overview', 'position': 100},
    {'name': 'OutageShield Actions', 'position': 101},
    {'name': 'OutageShield Dashboard Links', 'position': 102},
]

section_ids = {}
for section in sections:
    section_data = {
        'name': section['name'],
        'table': 'change_request',
        'caption': section['name'],
        'position': section['position'],
        'view': 'Default view'
    }
    check = make_request(f"/api/now/table/sys_ui_section?sysparm_query=name={urllib.parse.quote(section['name'])}^table=change_request&sysparm_limit=1")
    if check and check.get('result') and len(check['result']) > 0:
        section_ids[section['name']] = check['result'][0]['sys_id']
        print(f"   ⏭️  Exists: {section['name']}")
    else:
        result = make_request('/api/now/table/sys_ui_section', method='POST', data=section_data)
        if result and result.get('result'):
            section_ids[section['name']] = result['result']['sys_id']
            print(f"   ✅ Created: {section['name']}")

# Step 3: Add fields to sections
print("\n3. Adding fields to sections...")

section_fields = {
    'OutageShield Overview': [
        ('u_outageshield_incident_id', 0),
        ('u_outageshield_service', 1),
        ('u_outageshield_severity', 2),
        ('u_outageshield_status', 3),
        ('u_outageshield_approval_status', 4),
    ],
    'OutageShield Actions': [
        ('u_outageshield_approve_url', 0),
        ('u_outageshield_reject_url', 1),
    ],
    'OutageShield Dashboard Links': [
        ('u_outageshield_dashboard_url', 0),
        ('u_outageshield_investigation_url', 1),
        ('u_outageshield_rca_url', 2),
        ('u_outageshield_remediation_url', 3),
        ('u_outageshield_postmortem_url', 4),
        ('u_outageshield_impact_url', 5),
        ('u_outageshield_timeline_url', 6),
        ('u_outageshield_metrics_url', 7),
    ],
}

for section_name, fields_list in section_fields.items():
    section_id = section_ids.get(section_name)
    if not section_id:
        continue
    for field_name, position in fields_list:
        element_data = {'sys_ui_section': section_id, 'element': field_name, 'position': position, 'type': 'field'}
        check = make_request(f"/api/now/table/sys_ui_element?sysparm_query=sys_ui_section={section_id}^element={field_name}&sysparm_limit=1")
        if not (check and check.get('result') and len(check['result']) > 0):
            result = make_request('/api/now/table/sys_ui_element', method='POST', data=element_data)
            if result:
                print(f"   ✅ Added {field_name}")


# Step 4: Create UI Action buttons (including Approve/Reject)
print("\n4. Creating UI Action buttons...")

ui_actions = [
    # Approve Button
    {
        'name': '✅ Approve Remediation',
        'action_name': 'approve_remediation',
        'onclick': "window.open(g_form.getValue('u_outageshield_approve_url'), '_blank'); g_form.setValue('u_outageshield_approval_status', 'APPROVED');",
        'style': 'color: white; background-color: #28a745; border-color: #28a745;',
        'order': 50,
        'hint': 'Approve the AI-recommended remediation'
    },
    # Reject Button
    {
        'name': '❌ Reject Remediation',
        'action_name': 'reject_remediation',
        'onclick': "window.open(g_form.getValue('u_outageshield_reject_url'), '_blank'); g_form.setValue('u_outageshield_approval_status', 'REJECTED');",
        'style': 'color: white; background-color: #dc3545; border-color: #dc3545;',
        'order': 51,
        'hint': 'Reject the AI-recommended remediation'
    },
    # Dashboard Links
    {'name': '📊 Full Dashboard', 'action_name': 'view_dashboard', 'onclick': "window.open(g_form.getValue('u_outageshield_dashboard_url'), '_blank');", 'order': 100},
    {'name': '🔍 Investigation', 'action_name': 'view_investigation', 'onclick': "window.open(g_form.getValue('u_outageshield_investigation_url'), '_blank');", 'order': 101},
    {'name': '🎯 Root Cause', 'action_name': 'view_rca', 'onclick': "window.open(g_form.getValue('u_outageshield_rca_url'), '_blank');", 'order': 102},
    {'name': '🔧 Remediation', 'action_name': 'view_remediation', 'onclick': "window.open(g_form.getValue('u_outageshield_remediation_url'), '_blank');", 'order': 103},
    {'name': '📝 Postmortem', 'action_name': 'view_postmortem', 'onclick': "window.open(g_form.getValue('u_outageshield_postmortem_url'), '_blank');", 'order': 104},
]

for action in ui_actions:
    action_data = {
        'name': action['name'],
        'table': 'change_request',
        'action_name': action['action_name'],
        'active': True,
        'client': True,
        'form_button': True,
        'form_context_menu': False,
        'form_link': False,
        'onclick': action['onclick'],
        'condition': 'u_outageshield_incident_id != null && u_outageshield_incident_id != ""',
        'order': action['order'],
        'hint': action.get('hint', ''),
    }
    encoded_query = urllib.parse.quote(f"name={action['name']}^table=change_request")
    check = make_request(f"/api/now/table/sys_ui_action?sysparm_query={encoded_query}&sysparm_limit=1")
    if check and check.get('result') and len(check['result']) > 0:
        print(f"   ⏭️  Exists: {action['name']}")
    else:
        result = make_request('/api/now/table/sys_ui_action', method='POST', data=action_data)
        if result:
            print(f"   ✅ Created: {action['name']}")


# Step 5: Create organized UI Page with Approve/Reject buttons that call the API
print("\n5. Creating UI Page with API approval functionality...")

ui_page_html = f'''<?xml version="1.0" encoding="utf-8" ?>
<j:jelly trim="false" xmlns:j="jelly:core" xmlns:g="glide">

<g:evaluate var="jvar_data" object="true">
  var data = {{}};
  var chgNum = RP.getParameterValue('number') || '';
  if (chgNum) {{
    var gr = new GlideRecord('change_request');
    gr.addQuery('number', chgNum);
    gr.query();
    if (gr.next()) {{
      data.incident_id = gr.getValue('u_outageshield_incident_id') || 'N/A';
      data.service = gr.getValue('u_outageshield_service') || 'N/A';
      data.severity = gr.getValue('u_outageshield_severity') || '3';
      data.status = gr.getValue('u_outageshield_status') || 'N/A';
      data.approval = gr.getValue('u_outageshield_approval_status') || 'PENDING';
      data.change_number = chgNum;
      data.sys_id = gr.getUniqueValue();
      data.found = true;
    }} else {{
      data.incident_id = 'Not Found';
      data.service = 'N/A';
      data.severity = '0';
      data.status = 'N/A';
      data.approval = 'N/A';
      data.change_number = chgNum;
      data.found = false;
    }}
  }} else {{
    data.incident_id = 'No CHG Number';
    data.service = 'N/A';
    data.severity = '0';
    data.status = 'N/A';
    data.approval = 'N/A';
    data.change_number = '';
    data.found = false;
  }}
  data;
</g:evaluate>

<style>
  * {{ box-sizing: border-box; }}
  .os-container {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 400px; border-radius: 12px; }}
  .os-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
  .os-logo {{ display: flex; align-items: center; gap: 12px; }}
  .os-logo-icon {{ width: 48px; height: 48px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; }}
  .os-logo-text {{ color: #fff; font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
  .os-logo-sub {{ color: rgba(255,255,255,0.6); font-size: 12px; font-weight: 400; }}
  .os-badge {{ padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
  .os-badge-pending {{ background: rgba(255,193,7,0.2); color: #ffc107; border: 1px solid rgba(255,193,7,0.3); }}
  .os-badge-approved {{ background: rgba(76,175,80,0.2); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); }}
  .os-badge-rejected {{ background: rgba(244,67,54,0.2); color: #f44336; border: 1px solid rgba(244,67,54,0.3); }}
  .os-info-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .os-info-card {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); transition: all 0.2s ease; }}
  .os-info-card:hover {{ background: rgba(255,255,255,0.08); transform: translateY(-2px); }}
  .os-info-icon {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; margin-bottom: 12px; }}
  .os-info-icon-blue {{ background: rgba(102,126,234,0.2); }}
  .os-info-icon-purple {{ background: rgba(118,75,162,0.2); }}
  .os-info-icon-orange {{ background: rgba(255,152,0,0.2); }}
  .os-info-icon-red {{ background: rgba(220,53,69,0.2); }}
  .os-info-label {{ color: rgba(255,255,255,0.5); font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }}
  .os-info-value {{ color: #fff; font-size: 18px; font-weight: 600; }}
  .os-info-value-small {{ font-size: 14px; }}
  .os-severity {{ display: flex; align-items: center; gap: 8px; }}
  .os-severity-dot {{ width: 12px; height: 12px; border-radius: 50%; animation: pulse 2s infinite; }}
  .os-severity-1 {{ background: #4caf50; box-shadow: 0 0 10px rgba(76,175,80,0.5); }}
  .os-severity-2 {{ background: #8bc34a; box-shadow: 0 0 10px rgba(139,195,74,0.5); }}
  .os-severity-3 {{ background: #ffc107; box-shadow: 0 0 10px rgba(255,193,7,0.5); }}
  .os-severity-4 {{ background: #ff9800; box-shadow: 0 0 10px rgba(255,152,0,0.5); }}
  .os-severity-5 {{ background: #f44336; box-shadow: 0 0 10px rgba(244,67,54,0.5); }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
  .os-actions {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
  .os-btn {{ display: flex; align-items: center; justify-content: center; gap: 10px; padding: 18px 24px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: 15px; transition: all 0.2s ease; cursor: pointer; border: none; }}
  .os-btn:hover {{ transform: translateY(-3px); text-decoration: none; }}
  .os-btn:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
  .os-btn-view {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 15px rgba(102,126,234,0.4); }}
  .os-btn-view:hover {{ box-shadow: 0 6px 20px rgba(102,126,234,0.6); color: white; }}
  .os-btn-approve {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; box-shadow: 0 4px 15px rgba(56,239,125,0.3); }}
  .os-btn-approve:hover {{ box-shadow: 0 6px 20px rgba(56,239,125,0.5); color: white; }}
  .os-btn-reject {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; box-shadow: 0 4px 15px rgba(235,51,73,0.3); }}
  .os-btn-reject:hover {{ box-shadow: 0 6px 20px rgba(235,51,73,0.5); color: white; }}
  .os-btn-icon {{ font-size: 20px; }}
  .os-status-msg {{ margin-top: 20px; padding: 16px; border-radius: 8px; text-align: center; font-weight: 500; display: none; }}
  .os-status-success {{ background: rgba(76,175,80,0.2); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); display: block; }}
  .os-status-error {{ background: rgba(244,67,54,0.2); color: #f44336; border: 1px solid rgba(244,67,54,0.3); display: block; }}
  .os-status-loading {{ background: rgba(33,150,243,0.2); color: #2196f3; border: 1px solid rgba(33,150,243,0.3); display: block; }}
  .os-spinner {{ display: inline-block; width: 16px; height: 16px; border: 2px solid currentColor; border-radius: 50%; border-top-color: transparent; animation: spin 1s linear infinite; margin-right: 8px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>

<div class="os-container">
  <div class="os-header">
    <div class="os-logo">
      <div class="os-logo-icon">🛡️</div>
      <div>
        <div class="os-logo-text">OutageShield AI</div>
        <div class="os-logo-sub">Intelligent Incident Response</div>
      </div>
    </div>
    <div id="approvalBadge" class="os-badge os-badge-pending">${{jvar_data.approval}}</div>
  </div>
  
  <div class="os-info-grid">
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-blue">🎫</div>
      <div class="os-info-label">Incident ID</div>
      <div class="os-info-value os-info-value-small" id="incidentId">${{jvar_data.incident_id}}</div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-purple">⚙️</div>
      <div class="os-info-label">Service</div>
      <div class="os-info-value">${{jvar_data.service}}</div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-orange">📊</div>
      <div class="os-info-label">Severity</div>
      <div class="os-info-value">
        <div class="os-severity">
          <span class="os-severity-dot os-severity-${{jvar_data.severity}}"></span>
          SEV-${{jvar_data.severity}}
        </div>
      </div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-red">🔄</div>
      <div class="os-info-label">Status</div>
      <div class="os-info-value" id="statusValue">${{jvar_data.status}}</div>
    </div>
  </div>
  
  <div class="os-actions">
    <a href="{DASHBOARD_URL}/incidents/${{jvar_data.incident_id}}" target="_blank" class="os-btn os-btn-view">
      <span class="os-btn-icon">🔍</span>
      View Full Details
    </a>
    <button type="button" id="btnApprove" class="os-btn os-btn-approve" onclick="handleApproval('approved')">
      <span class="os-btn-icon">✓</span>
      Approve Remediation
    </button>
    <button type="button" id="btnReject" class="os-btn os-btn-reject" onclick="handleApproval('rejected')">
      <span class="os-btn-icon">✕</span>
      Reject
    </button>
  </div>
  
  <div id="statusMsg" class="os-status-msg"></div>
</div>

<script>
  var incidentId = '${{jvar_data.incident_id}}';
  var changeNumber = '${{jvar_data.change_number}}';
  var currentApproval = '${{jvar_data.approval}}';
  var apiUrl = "{API_URL}";
  
  function updateBadgeColor() {{
    var badge = document.getElementById('approvalBadge');
    badge.className = 'os-badge';
    if (currentApproval.toLowerCase() === 'approved') {{
      badge.className += ' os-badge-approved';
    }} else if (currentApproval.toLowerCase() === 'rejected') {{
      badge.className += ' os-badge-rejected';
    }} else {{
      badge.className += ' os-badge-pending';
    }}
  }}
  updateBadgeColor();
  
  function showStatus(message, type) {{
    var statusMsg = document.getElementById('statusMsg');
    statusMsg.className = 'os-status-msg os-status-' + type;
    statusMsg.innerHTML = message;
  }}
  
  function setButtonsDisabled(disabled) {{
    document.getElementById('btnApprove').disabled = disabled;
    document.getElementById('btnReject').disabled = disabled;
  }}
  
  function handleApproval(decision) {{
    if (!incidentId || incidentId === 'N/A' || incidentId === 'Not Found') {{
      showStatus('Error: No valid incident ID found', 'error');
      return;
    }}
    
    if (currentApproval.toLowerCase() === 'approved' || currentApproval.toLowerCase() === 'rejected') {{
      showStatus('This incident has already been ' + currentApproval.toLowerCase(), 'error');
      return;
    }}
    
    setButtonsDisabled(true);
    showStatus('<span class="os-spinner"></span>Processing ' + decision + '...', 'loading');
    
    var url = apiUrl + '/approve/' + incidentId;
    var payload = JSON.stringify({{
      decision: decision,
      responder: 'ServiceNow',
      change_number: changeNumber
    }});
    
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    
    xhr.onreadystatechange = function() {{
      if (xhr.readyState === 4) {{
        if (xhr.status === 200) {{
          currentApproval = decision.toUpperCase();
          document.getElementById('approvalBadge').textContent = currentApproval;
          updateBadgeColor();
          document.getElementById('statusValue').textContent = decision === 'approved' ? 'Approved' : 'Rejected';
          showStatus('✓ Remediation ' + decision + ' successfully! Step Functions workflow resumed.', 'success');
        }} else if (xhr.status === 409) {{
          var response = JSON.parse(xhr.responseText);
          showStatus('This approval has already been processed: ' + (response.status || decision), 'error');
          setButtonsDisabled(false);
        }} else {{
          var errorMsg = 'Error processing approval';
          try {{
            var response = JSON.parse(xhr.responseText);
            errorMsg = response.error || errorMsg;
          }} catch(e) {{}}
          showStatus('✗ ' + errorMsg, 'error');
          setButtonsDisabled(false);
        }}
      }}
    }};
    
    xhr.onerror = function() {{
      showStatus('✗ Network error. Please try again.', 'error');
      setButtonsDisabled(false);
    }};
    
    xhr.send(payload);
  }}
</script>

</j:jelly>'''

full_ui_page_html = ui_page_html

ui_page_data = {
    'name': 'outageshield_incident',
    'description': 'OutageShield Incident - Organized UX with Approve/Reject',
    'html': full_ui_page_html,
    'direct': True,
    'category': 'general'
}

check = make_request("/api/now/table/sys_ui_page?sysparm_query=name=outageshield_incident&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    sys_id = check['result'][0]['sys_id']
    make_request(f'/api/now/table/sys_ui_page/{sys_id}', method='PATCH', data=ui_page_data)
    print("   ✅ Updated UI Page")
else:
    result = make_request('/api/now/table/sys_ui_page', method='POST', data=ui_page_data)
    if result:
        print("   ✅ Created UI Page")


# Step 6: Create Application Navigator
print("\n6. Creating Application Navigator...")

app_menu_data = {'title': 'OutageShield', 'active': True, 'order': 100}
check = make_request("/api/now/table/sys_app_application?sysparm_query=title=OutageShield&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    app_menu_id = check['result'][0]['sys_id']
    print("   ⏭️  Application menu exists")
else:
    result = make_request('/api/now/table/sys_app_application', method='POST', data=app_menu_data)
    app_menu_id = result['result']['sys_id'] if result and result.get('result') else None
    if app_menu_id:
        print("   ✅ Created Application menu")

if app_menu_id:
    modules = [
        {'title': 'All Incidents', 'filter': 'u_outageshield_incident_idISNOTEMPTY', 'order': 100},
        {'title': 'Pending Approval', 'filter': 'u_outageshield_incident_idISNOTEMPTY^u_outageshield_approval_status=PENDING', 'order': 101},
        {'title': 'Approved', 'filter': 'u_outageshield_incident_idISNOTEMPTY^u_outageshield_approval_status=APPROVED', 'order': 102},
        {'title': 'Rejected', 'filter': 'u_outageshield_incident_idISNOTEMPTY^u_outageshield_approval_status=REJECTED', 'order': 103},
        {'title': 'Critical (SEV 4-5)', 'filter': 'u_outageshield_incident_idISNOTEMPTY^u_outageshield_severity>=4', 'order': 104},
    ]
    for module in modules:
        module_data = {
            'title': module['title'], 'application': app_menu_id, 'active': True,
            'order': module['order'], 'link_type': 'LIST', 'name': 'change_request', 'filter': module['filter']
        }
        encoded_title = urllib.parse.quote(module['title'])
        check = make_request(f"/api/now/table/sys_app_module?sysparm_query=title={encoded_title}&sysparm_limit=1")
        if check and check.get('result') and len(check['result']) > 0:
            print(f"   ⏭️  Exists: {module['title']}")
        else:
            result = make_request('/api/now/table/sys_app_module', method='POST', data=module_data)
            if result:
                print(f"   ✅ Created: {module['title']}")

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("  COMPLETE")
print("=" * 70)
print(f"\n  Database displayed:")
print(f"    • {len(incidents)} incidents")
print(f"    • {len(postmortems)} postmortems")
print(f"\n  ServiceNow UI created:")
print(f"    • Modern dark theme UI with gradient background")
print(f"    • Header with OutageShield logo and approval status badge")
print(f"    • 4 Info Cards:")
print(f"        - 🎫 Incident ID")
print(f"        - ⚙️ Service")
print(f"        - 📊 Severity (with animated indicator)")
print(f"        - 🔄 Status")
print(f"    • 3 Action Buttons:")
print(f"        - 🔍 View Full Details (purple gradient)")
print(f"        - ✓ Approve Remediation (green gradient)")
print(f"        - ✕ Reject (red gradient)")
print(f"\n  Dashboard: {DASHBOARD_URL}")
print(f"  Access: https://{sn_instance}/outageshield_incident.do?number=CHG0000001")
print("=" * 70)
