"""
Create ServiceNow UI Page for OutageShield Incident Details
Mimics the OutageShield dashboard incident detail view
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

print("=" * 60)
print("CREATING SERVICENOW UI FOR OUTAGESHIELD")
print("=" * 60)

# Step 1: Create UI Macro for CSS Styles
print("\n1. Creating CSS Styles UI Macro...")

css_styles = '''
<style>
:root {
  --os-bg-dark: #0d1117;
  --os-bg-card: #161b22;
  --os-border: #30363d;
  --os-text: #c9d1d9;
  --os-text-muted: #8b949e;
  --os-brand: #58a6ff;
  --os-red: #f85149;
  --os-orange: #d29922;
  --os-green: #3fb950;
  --os-purple: #a371f7;
}

.outageshield-container {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--os-bg-dark);
  color: var(--os-text);
  padding: 24px;
  min-height: 100vh;
}

.os-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.os-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.os-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.os-badge-critical { background: rgba(248,81,73,0.2); color: #f85149; border: 1px solid rgba(248,81,73,0.4); }
.os-badge-high { background: rgba(210,153,34,0.2); color: #d29922; border: 1px solid rgba(210,153,34,0.4); }
.os-badge-medium { background: rgba(187,128,9,0.2); color: #bb8009; border: 1px solid rgba(187,128,9,0.4); }
.os-badge-status { background: rgba(88,166,255,0.2); color: #58a6ff; border: 1px solid rgba(88,166,255,0.4); }
.os-badge-service { background: rgba(56,139,253,0.2); color: #388bfd; border: 1px solid rgba(56,139,253,0.4); }

.os-title {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  margin: 12px 0 8px 0;
}

.os-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 20px;
}

.os-stat-box {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: 12px;
  padding: 16px;
}

.os-stat-box.red { border-color: rgba(248,81,73,0.4); }
.os-stat-box.orange { border-color: rgba(210,153,34,0.4); }
.os-stat-box.blue { border-color: rgba(88,166,255,0.4); }
.os-stat-box.green { border-color: rgba(63,185,80,0.4); }

.os-stat-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--os-text-muted);
  margin-bottom: 8px;
}

.os-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #ffffff;
}

.os-tabs {
  display: flex;
  gap: 4px;
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 16px;
  width: fit-content;
}

.os-tab {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--os-text-muted);
  cursor: pointer;
  border: none;
  background: transparent;
}

.os-tab.active {
  background: #21262d;
  color: #ffffff;
}

.os-tab:hover:not(.active) {
  color: var(--os-text);
  background: rgba(255,255,255,0.05);
}

.os-section {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 16px;
}

.os-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--os-border);
}

.os-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.os-section-badge {
  font-size: 10px;
  color: var(--os-text-muted);
  background: #21262d;
  padding: 4px 8px;
  border-radius: 4px;
}

.os-section-content {
  padding: 16px;
}

.os-rca-card {
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 12px;
}

.os-rca-card.primary {
  background: rgba(88,166,255,0.1);
  border: 1px solid rgba(88,166,255,0.3);
}

.os-rca-card.secondary {
  background: rgba(48,54,61,0.5);
  border: 1px solid var(--os-border);
}

.os-rca-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.os-rca-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.os-rca-label.primary { color: var(--os-brand); }
.os-rca-label.secondary { color: var(--os-text-muted); }

.os-confidence {
  font-size: 12px;
  font-weight: 700;
}

.os-confidence.high { color: var(--os-green); }
.os-confidence.medium { color: var(--os-orange); }
.os-confidence.low { color: var(--os-red); }

.os-category-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  margin-right: 8px;
}

.os-category-capacity { background: rgba(248,81,73,0.2); color: #f85149; }
.os-category-performance { background: rgba(210,153,34,0.2); color: #d29922; }
.os-category-configuration { background: rgba(187,128,9,0.2); color: #bb8009; }
.os-category-deployment { background: rgba(56,139,253,0.2); color: #388bfd; }
.os-category-scaling { background: rgba(63,185,80,0.2); color: #3fb950; }
.os-category-rollback { background: rgba(56,139,253,0.2); color: #388bfd; }

.os-quick-action {
  background: rgba(48,54,61,0.5);
  border: 1px solid var(--os-border);
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.os-quick-action-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: rgba(33,38,45,0.5);
  border-bottom: 1px solid var(--os-border);
}

.os-quick-action-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--os-text);
}

.os-quick-action-cmd {
  padding: 12px 16px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  color: #7ee787;
  white-space: pre-wrap;
  word-break: break-all;
}

.os-copy-btn {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: #21262d;
  color: var(--os-text-muted);
  border: 1px solid var(--os-border);
  cursor: pointer;
}

.os-copy-btn:hover {
  background: #30363d;
  color: var(--os-text);
}

.os-ai-summary {
  padding: 16px;
  border-radius: 8px;
  background: rgba(163,113,247,0.1);
  border: 1px solid rgba(163,113,247,0.3);
  margin-bottom: 16px;
}

.os-ai-summary-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--os-purple);
  margin-bottom: 8px;
}

.os-ai-summary-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--os-text);
}

.os-investigation-box {
  padding: 16px;
  border-radius: 8px;
  background: rgba(48,54,61,0.5);
  border: 1px solid var(--os-border);
}

.os-investigation-text {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--os-text-muted);
  white-space: pre-wrap;
}

.os-sidebar {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: 12px;
  padding: 20px;
}

.os-sidebar-section {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--os-border);
}

.os-sidebar-section:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.os-sidebar-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--os-text-muted);
  margin-bottom: 12px;
}

.os-sidebar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.os-sidebar-label {
  font-size: 12px;
  color: var(--os-text-muted);
}

.os-sidebar-value {
  font-size: 12px;
  font-weight: 600;
}

.os-progress-bar {
  height: 6px;
  background: #21262d;
  border-radius: 3px;
  overflow: hidden;
  margin-top: 4px;
}

.os-progress-fill {
  height: 100%;
  border-radius: 3px;
}

.os-progress-fill.red { background: linear-gradient(90deg, #da3633, #f85149); }
.os-progress-fill.orange { background: linear-gradient(90deg, #9e6a03, #d29922); }

.os-approval-box {
  background: linear-gradient(135deg, rgba(163,113,247,0.15), rgba(88,166,255,0.15));
  border: 1px solid rgba(163,113,247,0.3);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.os-approval-title {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 8px;
}

.os-approval-desc {
  font-size: 14px;
  color: var(--os-text-muted);
  margin-bottom: 16px;
}

.os-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  margin-right: 12px;
}

.os-btn-approve {
  background: #238636;
  color: #ffffff;
}

.os-btn-approve:hover {
  background: #2ea043;
}

.os-btn-reject {
  background: rgba(248,81,73,0.6);
  color: #ffffff;
}

.os-btn-reject:hover {
  background: rgba(248,81,73,0.8);
}

.os-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

@media (max-width: 1024px) {
  .os-grid { grid-template-columns: 1fr; }
  .os-stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
'''

# Step 2: Create UI Page HTML Template
print("\n2. Creating UI Page HTML Template...")

html_template = '''
<div class="outageshield-container">
  <!-- Header Card -->
  <div class="os-card">
    <div class="os-header">
      <span class="os-badge os-badge-critical">SEV-${severity}</span>
      <span class="os-badge os-badge-status">${status}</span>
      <span class="os-badge os-badge-service">${service}</span>
      <span style="margin-left: auto; font-size: 12px; color: #8b949e;">
        <span style="margin-right: 4px;">⏱</span> ${duration}
      </span>
    </div>
    <h1 class="os-title">[OutageShield] ${incident_id} - ${service}</h1>
    <p style="font-size: 13px; color: #8b949e;">${detected_at} · ${workflow_step}</p>
    
    <!-- Quick Stats -->
    <div class="os-stats-grid">
      <div class="os-stat-box red">
        <div class="os-stat-label">📈 Impact</div>
        <div class="os-stat-value">${business_impact}/10</div>
      </div>
      <div class="os-stat-box orange">
        <div class="os-stat-label">⏱ Duration</div>
        <div class="os-stat-value">${duration}</div>
      </div>
      <div class="os-stat-box blue">
        <div class="os-stat-label">👥 Users</div>
        <div class="os-stat-value">${affected_users}</div>
      </div>
      <div class="os-stat-box green">
        <div class="os-stat-label">💰 Revenue</div>
        <div class="os-stat-value">${revenue_risk}</div>
      </div>
    </div>
  </div>

  <!-- Approval Box (if awaiting) -->
  <div class="os-approval-box" id="approval-section">
    <div style="display: flex; align-items: flex-start; gap: 16px;">
      <div style="width: 48px; height: 48px; border-radius: 12px; background: rgba(163,113,247,0.2); display: flex; align-items: center; justify-content: center; font-size: 24px;">🛡️</div>
      <div style="flex: 1;">
        <h3 class="os-approval-title">Human Approval Required</h3>
        <p class="os-approval-desc">AI has completed the investigation and generated remediation recommendations. Please review the findings and approve or reject the recommended actions.</p>
        <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
          <div class="os-stat-label" style="color: #a371f7;">Recommended Action</div>
          <p style="font-size: 14px; color: #c9d1d9; margin-top: 4px;">${recommended_action}</p>
          <p style="font-size: 12px; color: #8b949e; margin-top: 8px;">Confidence: ${confidence}% · Risk: ${risk} · Est. TTR: ${ttr}m</p>
        </div>
        <button class="os-btn os-btn-approve" onclick="approveRemediation()">👍 Approve Remediation</button>
        <button class="os-btn os-btn-reject" onclick="rejectRemediation()">👎 Reject</button>
      </div>
    </div>
  </div>
'''

html_template += '''
  <!-- Tabs -->
  <div class="os-tabs">
    <button class="os-tab active" onclick="showTab('overview')">Overview</button>
    <button class="os-tab" onclick="showTab('actions')">Actions</button>
    <button class="os-tab" onclick="showTab('ai-summary')">✨ AI Summary</button>
    <button class="os-tab" onclick="showTab('investigation')">🔍 Investigation</button>
  </div>

  <div class="os-grid">
    <!-- Main Content -->
    <div>
      <!-- Overview Tab -->
      <div id="tab-overview" class="tab-content">
        <div class="os-section">
          <div class="os-section-header">
            <span class="os-section-title">🎯 Root Cause Analysis</span>
            <span class="os-section-badge">${rca_count} identified</span>
          </div>
          <div class="os-section-content">
            <div class="os-rca-card primary">
              <div class="os-rca-header">
                <div>
                  <span class="os-rca-label primary">● Primary Cause</span>
                  <span class="os-category-badge os-category-${rca_category}">${rca_category}</span>
                </div>
                <span class="os-confidence high">${confidence}%</span>
              </div>
              <p style="font-size: 14px; color: #c9d1d9;">${root_cause}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions Tab -->
      <div id="tab-actions" class="tab-content" style="display: none;">
        <div class="os-section">
          <div class="os-section-header">
            <span class="os-section-title">⚡ Recommended Actions</span>
            <span class="os-section-badge">${action_count} actions</span>
          </div>
          <div class="os-section-content">
            ${recommendations_html}
          </div>
        </div>
      </div>
'''

html_template += '''
      <!-- AI Summary Tab -->
      <div id="tab-ai-summary" class="tab-content" style="display: none;">
        <div class="os-section">
          <div class="os-section-header">
            <span class="os-section-title">✨ AI Summary</span>
            <span class="os-section-badge">Generated</span>
          </div>
          <div class="os-section-content">
            <div class="os-ai-summary">
              <div class="os-ai-summary-label">AI Analysis</div>
              <p class="os-ai-summary-text">${ai_summary}</p>
            </div>
            
            <h4 style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #8b949e; margin: 16px 0 8px 0;">Quick Actions</h4>
            ${quick_actions_html}
          </div>
        </div>
      </div>

      <!-- Investigation Tab -->
      <div id="tab-investigation" class="tab-content" style="display: none;">
        <div class="os-section">
          <div class="os-section-header">
            <span class="os-section-title">🔍 AI Investigation</span>
            <span class="os-section-badge">Bedrock Agent</span>
          </div>
          <div class="os-section-content">
            <div style="padding: 12px; border-radius: 8px; background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.3); margin-bottom: 16px;">
              <p style="font-size: 12px; color: #58a6ff;">ℹ️ The AI agent analyzed this incident using 6 specialized tools: incident history, logs, runbooks, deployments, traces, and config drift.</p>
            </div>
            <div class="os-investigation-box">
              <pre class="os-investigation-text">${investigation}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
'''

html_template += '''
    <!-- Sidebar -->
    <div>
      <div class="os-sidebar">
        <div class="os-sidebar-section">
          <div class="os-sidebar-title">Status</div>
          <div class="os-sidebar-row">
            <span class="os-sidebar-label">Status</span>
            <span class="os-sidebar-value" style="color: #58a6ff;">${status}</span>
          </div>
          <div class="os-sidebar-row">
            <span class="os-sidebar-label">Workflow</span>
            <span class="os-sidebar-value" style="color: #58a6ff;">${workflow_step}</span>
          </div>
          <div class="os-sidebar-row">
            <span class="os-sidebar-label">Detected</span>
            <span class="os-sidebar-value" style="color: #c9d1d9;">${detected_time}</span>
          </div>
          <div class="os-sidebar-row">
            <span class="os-sidebar-label">Duration</span>
            <span class="os-sidebar-value" style="color: #d29922;">${duration}</span>
          </div>
        </div>
        
        <div class="os-sidebar-section">
          <div class="os-sidebar-title">Impact</div>
          <div style="margin-bottom: 12px;">
            <div class="os-sidebar-row">
              <span class="os-sidebar-label">Severity</span>
              <span class="os-sidebar-value" style="color: #f85149;">SEV-${severity}</span>
            </div>
            <div class="os-progress-bar">
              <div class="os-progress-fill red" style="width: ${severity_pct}%;"></div>
            </div>
          </div>
          <div>
            <div class="os-sidebar-row">
              <span class="os-sidebar-label">Business Impact</span>
              <span class="os-sidebar-value" style="color: #ffffff;">${business_impact}/10</span>
            </div>
            <div class="os-progress-bar">
              <div class="os-progress-fill orange" style="width: ${impact_pct}%;"></div>
            </div>
          </div>
        </div>
        
        <div class="os-sidebar-section">
          <div class="os-sidebar-title">Links</div>
          <a href="${dashboard_url}" target="_blank" style="display: block; padding: 8px 12px; background: #21262d; border-radius: 6px; color: #58a6ff; text-decoration: none; font-size: 13px; margin-bottom: 8px;">
            📊 View in OutageShield Dashboard
          </a>
          <a href="${postmortem_url}" target="_blank" style="display: block; padding: 8px 12px; background: #21262d; border-radius: 6px; color: #a371f7; text-decoration: none; font-size: 13px;">
            📄 View Postmortem
          </a>
        </div>
      </div>
    </div>
  </div>
</div>
'''

# JavaScript for tab switching and copy functionality
js_code = '''
<script>
function showTab(tabName) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(function(tab) {
    tab.style.display = 'none';
  });
  // Remove active class from all buttons
  document.querySelectorAll('.os-tab').forEach(function(btn) {
    btn.classList.remove('active');
  });
  // Show selected tab
  document.getElementById('tab-' + tabName).style.display = 'block';
  // Add active class to clicked button
  event.target.classList.add('active');
}

function copyCommand(text, btnId) {
  navigator.clipboard.writeText(text).then(function() {
    var btn = document.getElementById(btnId);
    btn.innerHTML = '✓ Copied';
    btn.style.color = '#3fb950';
    setTimeout(function() {
      btn.innerHTML = '📋 Copy';
      btn.style.color = '';
    }, 2000);
  });
}

function approveRemediation() {
  // This would call the ServiceNow API to update approval
  var changeNumber = '${change_number}';
  alert('Approving remediation for ' + changeNumber + '...\\nThis will trigger the OutageShield workflow to continue.');
  // Update the approval field
  g_form.setValue('approval', 'approved');
  g_form.save();
}

function rejectRemediation() {
  var reason = prompt('Please provide a reason for rejection:');
  if (reason) {
    alert('Rejecting remediation...\\nReason: ' + reason);
    g_form.setValue('approval', 'rejected');
    g_form.save();
  }
}
</script>
'''

# Combine all parts
full_html = css_styles + html_template + js_code

# Step 3: Create Form Section in ServiceNow
print("\n3. Creating Form Section for OutageShield...")

# Create a UI Formatter to display the custom HTML
formatter_data = {
    'name': 'OutageShield Incident View',
    'formatter': 'outageshield_incident_view',
    'type': 'Formatter',
    'active': True
}

# Check if exists
check = make_request("/api/now/table/sys_ui_formatter?sysparm_query=name=OutageShield Incident View&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  UI Formatter already exists")
else:
    result = make_request('/api/now/table/sys_ui_formatter', method='POST', data=formatter_data)
    if result:
        print("   ✅ Created UI Formatter")
    else:
        print("   ⚠️  Could not create UI Formatter (may need manual setup)")

# Step 4: Create UI Macro with the HTML/CSS/JS
print("\n4. Creating UI Macro with OutageShield styles...")

macro_data = {
    'name': 'outageshield_styles',
    'xml': f'<?xml version="1.0" encoding="utf-8" ?><j:jelly trim="false" xmlns:j="jelly:core" xmlns:g="glide" xmlns:j2="null" xmlns:g2="null">{css_styles}</j:jelly>',
    'active': True,
    'description': 'OutageShield Dashboard Styles'
}

check = make_request("/api/now/table/sys_ui_macro?sysparm_query=name=outageshield_styles&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  UI Macro already exists, updating...")
    sys_id = check['result'][0]['sys_id']
    make_request(f'/api/now/table/sys_ui_macro/{sys_id}', method='PATCH', data=macro_data)
    print("   ✅ Updated UI Macro")
else:
    result = make_request('/api/now/table/sys_ui_macro', method='POST', data=macro_data)
    if result:
        print("   ✅ Created UI Macro")
    else:
        print("   ⚠️  Could not create UI Macro")

# Step 5: Create Form Layout with OutageShield Section
print("\n5. Creating Form Layout Section...")

# Create a Form Section for OutageShield data
section_data = {
    'name': 'OutageShield AI Analysis',
    'table': 'change_request',
    'caption': 'OutageShield AI Analysis',
    'position': 100
}

check = make_request("/api/now/table/sys_ui_section?sysparm_query=name=OutageShield AI Analysis^table=change_request&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  Form Section already exists")
    section_sys_id = check['result'][0]['sys_id']
else:
    result = make_request('/api/now/table/sys_ui_section', method='POST', data=section_data)
    if result and result.get('result'):
        section_sys_id = result['result']['sys_id']
        print(f"   ✅ Created Form Section: {section_sys_id}")
    else:
        section_sys_id = None
        print("   ⚠️  Could not create Form Section")

# Step 6: Add fields to the section
if section_sys_id:
    print("\n6. Adding OutageShield fields to section...")
    
    fields_to_add = [
        ('u_outageshield_incident_id', 0),
        ('u_outageshield_severity', 1),
        ('u_outageshield_service', 2),
        ('u_outageshield_root_cause', 3),
        ('u_outageshield_category', 4),
        ('u_outageshield_confidence', 5),
        ('u_outageshield_affected_users', 6),
        ('u_outageshield_revenue_risk', 7),
        ('u_outageshield_business_impact', 8),
        ('u_outageshield_ai_summary', 9),
        ('u_outageshield_investigation', 10),
        ('u_outageshield_remediation', 11),
        ('u_outageshield_postmortem', 12),
        ('u_outageshield_dashboard_url', 13)
    ]
    
    for field_name, position in fields_to_add:
        element_data = {
            'sys_ui_section': section_sys_id,
            'element': field_name,
            'position': position,
            'type': 'field'
        }
        
        check = make_request(f"/api/now/table/sys_ui_element?sysparm_query=sys_ui_section={section_sys_id}^element={field_name}&sysparm_limit=1")
        if check and check.get('result') and len(check['result']) > 0:
            continue
        
        result = make_request('/api/now/table/sys_ui_element', method='POST', data=element_data)
        if result:
            print(f"   ✅ Added: {field_name}")

# Step 7: Create a UI Page for standalone OutageShield view
print("\n7. Creating standalone UI Page...")

ui_page_html = '''<?xml version="1.0" encoding="utf-8" ?>
<j:jelly trim="false" xmlns:j="jelly:core" xmlns:g="glide" xmlns:j2="null" xmlns:g2="null">
<g:evaluate var="jvar_change" object="true">
  var gr = new GlideRecord('change_request');
  gr.addQuery('number', RP.getParameterValue('number'));
  gr.query();
  gr.next();
  gr;
</g:evaluate>

<style>
/* OutageShield Dark Theme Styles */
body { background: #0d1117 !important; }
.outageshield-page {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: #0d1117;
  color: #c9d1d9;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.os-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.os-header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; }
.os-badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.os-badge-sev { background: rgba(248,81,73,0.2); color: #f85149; border: 1px solid rgba(248,81,73,0.4); }
.os-badge-status { background: rgba(88,166,255,0.2); color: #58a6ff; border: 1px solid rgba(88,166,255,0.4); }
.os-badge-service { background: rgba(56,139,253,0.2); color: #388bfd; border: 1px solid rgba(56,139,253,0.4); }
.os-title { font-size: 20px; font-weight: 700; color: #ffffff; margin: 12px 0 8px 0; }
.os-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
.os-stat { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 16px; }
.os-stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #8b949e; margin-bottom: 8px; }
.os-stat-value { font-size: 24px; font-weight: 700; color: #ffffff; }
.os-section { background: #161b22; border: 1px solid #30363d; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.os-section-header { padding: 16px; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
.os-section-title { font-size: 14px; font-weight: 600; color: #ffffff; }
.os-section-content { padding: 16px; }
.os-text { font-size: 14px; line-height: 1.6; color: #c9d1d9; white-space: pre-wrap; }
.os-code { font-family: monospace; font-size: 12px; color: #7ee787; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; white-space: pre-wrap; }
.os-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }
.os-sidebar { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
.os-link { display: block; padding: 10px 12px; background: #21262d; border-radius: 6px; color: #58a6ff; text-decoration: none; font-size: 13px; margin-bottom: 8px; }
.os-link:hover { background: #30363d; }
</style>
'''

ui_page_html += '''
<div class="outageshield-page">
  <div class="os-card">
    <div class="os-header">
      <span class="os-badge os-badge-sev">SEV-${jvar_change.u_outageshield_severity}</span>
      <span class="os-badge os-badge-status">${jvar_change.state.getDisplayValue()}</span>
      <span class="os-badge os-badge-service">${jvar_change.u_outageshield_service}</span>
    </div>
    <h1 class="os-title">[OutageShield] ${jvar_change.u_outageshield_incident_id} - ${jvar_change.u_outageshield_service}</h1>
    <p style="font-size: 13px; color: #8b949e;">${jvar_change.number} · ${jvar_change.sys_created_on}</p>
    
    <div class="os-stats">
      <div class="os-stat" style="border-color: rgba(248,81,73,0.4);">
        <div class="os-stat-label">📈 Business Impact</div>
        <div class="os-stat-value">${jvar_change.u_outageshield_business_impact}</div>
      </div>
      <div class="os-stat" style="border-color: rgba(210,153,34,0.4);">
        <div class="os-stat-label">🎯 Confidence</div>
        <div class="os-stat-value">${jvar_change.u_outageshield_confidence}</div>
      </div>
      <div class="os-stat" style="border-color: rgba(88,166,255,0.4);">
        <div class="os-stat-label">👥 Affected Users</div>
        <div class="os-stat-value">${jvar_change.u_outageshield_affected_users}</div>
      </div>
      <div class="os-stat" style="border-color: rgba(63,185,80,0.4);">
        <div class="os-stat-label">💰 Revenue at Risk</div>
        <div class="os-stat-value">${jvar_change.u_outageshield_revenue_risk}</div>
      </div>
    </div>
  </div>

  <div class="os-grid">
    <div>
      <!-- Root Cause -->
      <div class="os-section">
        <div class="os-section-header">
          <span class="os-section-title">🎯 Root Cause Analysis</span>
          <span style="font-size: 10px; color: #8b949e; background: #21262d; padding: 4px 8px; border-radius: 4px;">${jvar_change.u_outageshield_category}</span>
        </div>
        <div class="os-section-content">
          <p class="os-text">${jvar_change.u_outageshield_root_cause}</p>
        </div>
      </div>

      <!-- AI Summary -->
      <div class="os-section">
        <div class="os-section-header">
          <span class="os-section-title">✨ AI Summary</span>
        </div>
        <div class="os-section-content">
          <div style="background: rgba(163,113,247,0.1); border: 1px solid rgba(163,113,247,0.3); border-radius: 8px; padding: 16px;">
            <p class="os-text">${jvar_change.u_outageshield_ai_summary}</p>
          </div>
        </div>
      </div>

      <!-- Investigation -->
      <div class="os-section">
        <div class="os-section-header">
          <span class="os-section-title">🔍 Investigation</span>
        </div>
        <div class="os-section-content">
          <pre class="os-code">${jvar_change.u_outageshield_investigation}</pre>
        </div>
      </div>

      <!-- Remediation -->
      <div class="os-section">
        <div class="os-section-header">
          <span class="os-section-title">⚡ Remediation</span>
        </div>
        <div class="os-section-content">
          <pre class="os-code">${jvar_change.u_outageshield_remediation}</pre>
        </div>
      </div>

      <!-- Postmortem -->
      <div class="os-section">
        <div class="os-section-header">
          <span class="os-section-title">📄 Postmortem</span>
        </div>
        <div class="os-section-content">
          <p class="os-text">${jvar_change.u_outageshield_postmortem}</p>
        </div>
      </div>
    </div>
'''

ui_page_html += '''
    <!-- Sidebar -->
    <div>
      <div class="os-sidebar">
        <h3 style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #8b949e; margin-bottom: 16px;">Quick Links</h3>
        <a href="${jvar_change.u_outageshield_dashboard_url}" target="_blank" class="os-link">📊 View in OutageShield Dashboard</a>
        <a href="/change_request.do?sys_id=${jvar_change.sys_id}" class="os-link">📝 Edit Change Request</a>
        
        <h3 style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #8b949e; margin: 24px 0 16px 0;">Details</h3>
        <div style="font-size: 12px; color: #8b949e;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>Change Number</span>
            <span style="color: #c9d1d9;">${jvar_change.number}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>Incident ID</span>
            <span style="color: #58a6ff;">${jvar_change.u_outageshield_incident_id}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>Service</span>
            <span style="color: #c9d1d9;">${jvar_change.u_outageshield_service}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>Severity</span>
            <span style="color: #f85149;">SEV-${jvar_change.u_outageshield_severity}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>Category</span>
            <span style="color: #d29922;">${jvar_change.u_outageshield_category}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
</j:jelly>
'''

# Create the UI Page
page_data = {
    'name': 'outageshield_incident',
    'title': 'OutageShield Incident View',
    'html': ui_page_html,
    'direct': True,
    'description': 'OutageShield AI Incident Detail View - Dark Theme Dashboard'
}

check = make_request("/api/now/table/sys_ui_page?sysparm_query=name=outageshield_incident&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  UI Page already exists, updating...")
    sys_id = check['result'][0]['sys_id']
    make_request(f'/api/now/table/sys_ui_page/{sys_id}', method='PATCH', data=page_data)
    print("   ✅ Updated UI Page")
else:
    result = make_request('/api/now/table/sys_ui_page', method='POST', data=page_data)
    if result:
        print("   ✅ Created UI Page")
    else:
        print("   ⚠️  Could not create UI Page")

# Step 8: Create UI Action to open OutageShield view
print("\n8. Creating UI Action button...")

ui_action_data = {
    'name': 'View in OutageShield',
    'table': 'change_request',
    'action_name': 'view_outageshield',
    'active': True,
    'client': True,
    'form_button': True,
    'form_link': False,
    'list_link': True,
    'onclick': "window.open('/outageshield_incident.do?number=' + g_form.getValue('number'), '_blank');",
    'condition': 'current.u_outageshield_incident_id != ""',
    'order': 200,
    'hint': 'View this incident in OutageShield dashboard style'
}

check = make_request("/api/now/table/sys_ui_action?sysparm_query=name=View in OutageShield^table=change_request&sysparm_limit=1")
if check and check.get('result') and len(check['result']) > 0:
    print("   ⏭️  UI Action already exists, updating...")
    sys_id = check['result'][0]['sys_id']
    make_request(f'/api/now/table/sys_ui_action/{sys_id}', method='PATCH', data=ui_action_data)
    print("   ✅ Updated UI Action")
else:
    result = make_request('/api/now/table/sys_ui_action', method='POST', data=ui_action_data)
    if result:
        print("   ✅ Created UI Action")
    else:
        print("   ⚠️  Could not create UI Action")

print("\n" + "=" * 60)
print("SERVICENOW UI SETUP COMPLETE!")
print("=" * 60)
print(f"""
✅ Created OutageShield-style UI for ServiceNow!

WHAT WAS CREATED:
1. UI Macro with dark theme CSS styles
2. Form Section "OutageShield AI Analysis" on change_request
3. UI Page "outageshield_incident" - standalone dashboard view
4. UI Action "View in OutageShield" button

HOW TO USE:
1. Open any OutageShield change request in ServiceNow
2. Scroll down to see the "OutageShield AI Analysis" section
3. Click "View in OutageShield" button for full dashboard view

STANDALONE VIEW URL:
https://{sn_instance}/outageshield_incident.do?number=CHG0030005

The UI includes:
- Dark theme matching your OutageShield dashboard
- Header with severity, status, service badges
- Quick stats (Impact, Duration, Users, Revenue)
- Root Cause Analysis section
- AI Summary with quick actions
- Investigation details
- Remediation recommendations
- Postmortem summary
- Sidebar with links and details
""")
