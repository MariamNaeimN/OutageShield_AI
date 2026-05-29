"""
Fix the OutageShield UI Page to actually call the approval API when Approve/Reject is clicked.
The buttons now make AJAX calls to the Dashboard API to resume Step Functions.
"""
import boto3
import json
import base64
import urllib.request
import urllib.error

ssm = boto3.client('ssm', region_name='us-east-1')

# Get ServiceNow credentials
sn_instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

DASHBOARD_URL = "https://d2k1km1tzlio49.cloudfront.net"
API_URL = "https://601lnlm7r5.execute-api.us-east-1.amazonaws.com/dev"

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
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

print("Updating OutageShield UI Page with API approval calls...")

# Fixed UI Page HTML with JavaScript to call the approval API
ui_page_html = '''<?xml version="1.0" encoding="utf-8" ?>
<j:jelly trim="false" xmlns:j="jelly:core" xmlns:g="glide">

<g:evaluate var="jvar_data" object="true">
  var data = {};
  var chgNum = RP.getParameterValue('number') || '';
  if (chgNum) {
    var gr = new GlideRecord('change_request');
    gr.addQuery('number', chgNum);
    gr.query();
    if (gr.next()) {
      data.incident_id = gr.getValue('u_outageshield_incident_id') || 'N/A';
      data.service = gr.getValue('u_outageshield_service') || 'N/A';
      data.severity = gr.getValue('u_outageshield_severity') || '3';
      data.status = gr.getValue('u_outageshield_status') || 'N/A';
      data.approval = gr.getValue('u_outageshield_approval_status') || 'PENDING';
      data.change_number = chgNum;
      data.sys_id = gr.getUniqueValue();
      data.found = true;
    } else {
      data.incident_id = 'Not Found';
      data.service = 'N/A';
      data.severity = '0';
      data.status = 'N/A';
      data.approval = 'N/A';
      data.change_number = chgNum;
      data.found = false;
    }
  } else {
    data.incident_id = 'No CHG Number';
    data.service = 'N/A';
    data.severity = '0';
    data.status = 'N/A';
    data.approval = 'N/A';
    data.change_number = '';
    data.found = false;
  }
  data;
</g:evaluate>

<style>
  * { box-sizing: border-box; }
  .os-container { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 400px; border-radius: 12px; }
  .os-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); }
  .os-logo { display: flex; align-items: center; gap: 12px; }
  .os-logo-icon { width: 48px; height: 48px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; }
  .os-logo-text { color: #fff; font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
  .os-logo-sub { color: rgba(255,255,255,0.6); font-size: 12px; font-weight: 400; }
  .os-badge { padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .os-badge-pending { background: rgba(255,193,7,0.2); color: #ffc107; border: 1px solid rgba(255,193,7,0.3); }
  .os-badge-approved { background: rgba(76,175,80,0.2); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); }
  .os-badge-rejected { background: rgba(244,67,54,0.2); color: #f44336; border: 1px solid rgba(244,67,54,0.3); }
  .os-info-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .os-info-card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); transition: all 0.2s ease; }
  .os-info-card:hover { background: rgba(255,255,255,0.08); transform: translateY(-2px); }
  .os-info-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; margin-bottom: 12px; }
  .os-info-icon-blue { background: rgba(102,126,234,0.2); }
  .os-info-icon-purple { background: rgba(118,75,162,0.2); }
  .os-info-icon-orange { background: rgba(255,152,0,0.2); }
  .os-info-icon-red { background: rgba(220,53,69,0.2); }
  .os-info-label { color: rgba(255,255,255,0.5); font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
  .os-info-value { color: #fff; font-size: 18px; font-weight: 600; }
  .os-info-value-small { font-size: 14px; }
  .os-severity { display: flex; align-items: center; gap: 8px; }
  .os-severity-dot { width: 12px; height: 12px; border-radius: 50%; animation: pulse 2s infinite; }
  .os-severity-1 { background: #4caf50; box-shadow: 0 0 10px rgba(76,175,80,0.5); }
  .os-severity-2 { background: #8bc34a; box-shadow: 0 0 10px rgba(139,195,74,0.5); }
  .os-severity-3 { background: #ffc107; box-shadow: 0 0 10px rgba(255,193,7,0.5); }
  .os-severity-4 { background: #ff9800; box-shadow: 0 0 10px rgba(255,152,0,0.5); }
  .os-severity-5 { background: #f44336; box-shadow: 0 0 10px rgba(244,67,54,0.5); }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
  .os-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .os-btn { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 18px 24px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: 15px; transition: all 0.2s ease; cursor: pointer; border: none; }
  .os-btn:hover { transform: translateY(-3px); text-decoration: none; }
  .os-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .os-btn-view { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 15px rgba(102,126,234,0.4); }
  .os-btn-view:hover { box-shadow: 0 6px 20px rgba(102,126,234,0.6); color: white; }
  .os-btn-approve { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; box-shadow: 0 4px 15px rgba(56,239,125,0.3); }
  .os-btn-approve:hover { box-shadow: 0 6px 20px rgba(56,239,125,0.5); color: white; }
  .os-btn-reject { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; box-shadow: 0 4px 15px rgba(235,51,73,0.3); }
  .os-btn-reject:hover { box-shadow: 0 6px 20px rgba(235,51,73,0.5); color: white; }
  .os-btn-icon { font-size: 20px; }
  .os-status-msg { margin-top: 20px; padding: 16px; border-radius: 8px; text-align: center; font-weight: 500; display: none; }
  .os-status-success { background: rgba(76,175,80,0.2); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); display: block; }
  .os-status-error { background: rgba(244,67,54,0.2); color: #f44336; border: 1px solid rgba(244,67,54,0.3); display: block; }
  .os-status-loading { background: rgba(33,150,243,0.2); color: #2196f3; border: 1px solid rgba(33,150,243,0.3); display: block; }
  .os-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid currentColor; border-radius: 50%; border-top-color: transparent; animation: spin 1s linear infinite; margin-right: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
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
    <div id="approvalBadge" class="os-badge os-badge-pending">${jvar_data.approval}</div>
  </div>
  
  <div class="os-info-grid">
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-blue">🎫</div>
      <div class="os-info-label">Incident ID</div>
      <div class="os-info-value os-info-value-small" id="incidentId">${jvar_data.incident_id}</div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-purple">⚙️</div>
      <div class="os-info-label">Service</div>
      <div class="os-info-value">${jvar_data.service}</div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-orange">📊</div>
      <div class="os-info-label">Severity</div>
      <div class="os-info-value">
        <div class="os-severity">
          <span class="os-severity-dot os-severity-${jvar_data.severity}"></span>
          SEV-${jvar_data.severity}
        </div>
      </div>
    </div>
    <div class="os-info-card">
      <div class="os-info-icon os-info-icon-red">🔄</div>
      <div class="os-info-label">Status</div>
      <div class="os-info-value" id="statusValue">${jvar_data.status}</div>
    </div>
  </div>
  
  <div class="os-actions">
    <a href="''' + DASHBOARD_URL + '''/incidents/${jvar_data.incident_id}" target="_blank" class="os-btn os-btn-view">
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
  var incidentId = '${jvar_data.incident_id}';
  var changeNumber = '${jvar_data.change_number}';
  var currentApproval = '${jvar_data.approval}';
  var apiUrl = "''' + API_URL + '''";
  
  // Update badge color based on current status
  function updateBadgeColor() {
    var badge = document.getElementById('approvalBadge');
    badge.className = 'os-badge';
    if (currentApproval.toLowerCase() === 'approved') {
      badge.className += ' os-badge-approved';
    } else if (currentApproval.toLowerCase() === 'rejected') {
      badge.className += ' os-badge-rejected';
    } else {
      badge.className += ' os-badge-pending';
    }
  }
  updateBadgeColor();
  
  function showStatus(message, type) {
    var statusMsg = document.getElementById('statusMsg');
    statusMsg.className = 'os-status-msg os-status-' + type;
    statusMsg.innerHTML = message;
  }
  
  function setButtonsDisabled(disabled) {
    document.getElementById('btnApprove').disabled = disabled;
    document.getElementById('btnReject').disabled = disabled;
  }
  
  function handleApproval(decision) {
    if (!incidentId || incidentId === 'N/A' || incidentId === 'Not Found') {
      showStatus('Error: No valid incident ID found', 'error');
      return;
    }
    
    // Check if already processed
    if (currentApproval.toLowerCase() === 'approved' || currentApproval.toLowerCase() === 'rejected') {
      showStatus('This incident has already been ' + currentApproval.toLowerCase(), 'error');
      return;
    }
    
    setButtonsDisabled(true);
    showStatus('<span class="os-spinner"></span>Processing ' + decision + '...', 'loading');
    
    var url = apiUrl + '/approve/' + incidentId;
    var payload = JSON.stringify({
      decision: decision,
      responder: 'ServiceNow',
      change_number: changeNumber
    });
    
    // Use XMLHttpRequest for cross-origin request
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    
    xhr.onreadystatechange = function() {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          var response = JSON.parse(xhr.responseText);
          currentApproval = decision.toUpperCase();
          document.getElementById('approvalBadge').textContent = currentApproval;
          updateBadgeColor();
          document.getElementById('statusValue').textContent = decision === 'approved' ? 'Approved' : 'Rejected';
          showStatus('✓ Remediation ' + decision + ' successfully! Step Functions workflow resumed.', 'success');
          
          // Also update ServiceNow change request
          updateServiceNowChange(decision);
        } else if (xhr.status === 409) {
          var response = JSON.parse(xhr.responseText);
          showStatus('This approval has already been processed: ' + (response.status || decision), 'error');
          setButtonsDisabled(false);
        } else {
          var errorMsg = 'Error processing approval';
          try {
            var response = JSON.parse(xhr.responseText);
            errorMsg = response.error || errorMsg;
          } catch(e) {}
          showStatus('✗ ' + errorMsg, 'error');
          setButtonsDisabled(false);
        }
      }
    };
    
    xhr.onerror = function() {
      showStatus('✗ Network error. Please try again.', 'error');
      setButtonsDisabled(false);
    };
    
    xhr.send(payload);
  }
  
  function updateServiceNowChange(decision) {
    // Update the ServiceNow change request approval status field
    if (!changeNumber) return;
    
    var gr = new GlideRecord('change_request');
    gr.addQuery('number', changeNumber);
    gr.query();
    if (gr.next()) {
      gr.setValue('u_outageshield_approval_status', decision.toUpperCase());
      gr.setValue('u_outageshield_status', decision === 'approved' ? 'Mitigating' : 'Rejected');
      gr.update();
    }
  }
</script>

</j:jelly>'''

ui_page_data = {
    'name': 'outageshield_incident',
    'description': 'OutageShield Incident - Modern UI with API Approval',
    'html': ui_page_html,
    'direct': True,
    'category': 'general'
}

# Find and update the UI Page
check = make_request("/api/now/table/sys_ui_page?sysparm_query=name=outageshield_incident&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    sys_id = check['result'][0]['sys_id']
    result = make_request(f'/api/now/table/sys_ui_page/{sys_id}', method='PATCH', data=ui_page_data)
    if result:
        print("✅ Updated UI Page successfully!")
    else:
        print("❌ Failed to update UI Page")
else:
    result = make_request('/api/now/table/sys_ui_page', method='POST', data=ui_page_data)
    if result:
        print("✅ Created UI Page successfully!")
    else:
        print("❌ Failed to create UI Page")

print(f"""
✅ UI Page updated with API approval functionality!

Changes:
1. Approve/Reject buttons now call the Dashboard API:
   POST {API_URL}/approve/{{incident_id}}
   Body: {{"decision": "approved/rejected", "responder": "ServiceNow"}}

2. This resumes the Step Functions workflow via SendTaskSuccess/SendTaskFailure

3. UI shows loading spinner and success/error messages

4. Badge color changes based on approval status

5. Also updates ServiceNow change request fields

Test URL: https://{sn_instance}/outageshield_incident.do?number=CHG0030063
""")
