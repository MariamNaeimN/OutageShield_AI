"""
OutageShield AI — Reset & Push 100 Incidents
=============================================
This script:
1. Clears ALL DynamoDB tables (fresh start)
2. Deletes ALL Jira tickets in the TGSHLD project
3. Triggers 100 incidents through the full agent pipeline

Run: python scripts/reset-and-push-100.py
Wait: ~15-20 minutes for all Bedrock analysis to complete
"""

import boto3
import json
import time
import random
import urllib.request
import urllib.error
import base64

REGION = 'us-east-1'
lambda_client = boto3.client('lambda', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sm = boto3.client('secretsmanager', region_name=REGION)

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Get Jira credentials from Secrets Manager
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  OutageShield AI — RESET & PUSH 100 INCIDENTS")
print("=" * 70)

print("\n[0/3] Loading Jira credentials from Secrets Manager...")
try:
    secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
    creds = json.loads(secret['SecretString'])
    JIRA_URL = creds['jira_url']
    PROJECT_KEY = creds['project_key']
    JIRA_EMAIL = creds['email']
    JIRA_TOKEN = creds['api_token']
    print(f"  ✓ Jira: {JIRA_URL} | Project: {PROJECT_KEY}")
except Exception as e:
    print(f"  ✗ Failed to get Jira credentials: {e}")
    print("  Continuing without Jira cleanup...")
    JIRA_URL = None

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Clear all DynamoDB tables
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/3] Clearing ALL DynamoDB tables...")
for table_name in ['outageshield-incidents-dev', 'outageshield-events-dev',
                   'outageshield-workflow-state-dev', 'outageshield-postmortems-dev']:
    try:
        table = dynamodb.Table(table_name)
        key_name = table.key_schema[0]['AttributeName']
        response = table.scan(ProjectionExpression=key_name)
        items = response.get('Items', [])
        for item in items:
            table.delete_item(Key={key_name: item[key_name]})
        while 'LastEvaluatedKey' in response:
            response = table.scan(ProjectionExpression=key_name, ExclusiveStartKey=response['LastEvaluatedKey'])
            for item in response.get('Items', []):
                table.delete_item(Key={key_name: item[key_name]})
            items.extend(response.get('Items', []))
        print(f"  ✓ Cleared {table_name} ({len(items)} items)")
    except Exception as e:
        print(f"  ✗ Failed to clear {table_name}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Delete all Jira tickets in TGSHLD project
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/3] Deleting ALL Jira tickets in project TGSHLD...")

if JIRA_URL:
    auth_bytes = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    deleted_count = 0
    start_at = 0
    batch_size = 50

    while True:
        # Search for all issues in the project
        jql = f"project={PROJECT_KEY} ORDER BY created DESC"
        search_url = f"{JIRA_URL}/rest/api/2/search?jql={urllib.parse.quote(jql)}&startAt={start_at}&maxResults={batch_size}&fields=key"

        try:
            import urllib.parse
            req = urllib.request.Request(search_url)
            req.add_header('Authorization', f'Basic {auth_bytes}')
            req.add_header('Accept', 'application/json')
            response = urllib.request.urlopen(req)
            data = json.loads(response.read().decode())
            issues = data.get('issues', [])

            if not issues:
                break

            for issue in issues:
                issue_key = issue['key']
                try:
                    del_url = f"{JIRA_URL}/rest/api/2/issue/{issue_key}"
                    del_req = urllib.request.Request(del_url, method='DELETE')
                    del_req.add_header('Authorization', f'Basic {auth_bytes}')
                    urllib.request.urlopen(del_req)
                    deleted_count += 1
                    print(f"    ✓ Deleted {issue_key}")
                except Exception as e:
                    print(f"    ✗ Failed to delete {issue_key}: {e}")

            # If we got fewer than batch_size, we're done
            if len(issues) < batch_size:
                break

            # Don't increment start_at since we're deleting items
            time.sleep(1)  # Rate limit

        except Exception as e:
            print(f"  ✗ Jira search failed: {e}")
            break

    print(f"  ✓ Deleted {deleted_count} Jira tickets")
else:
    print("  ⚠ Skipped (no Jira credentials)")

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Trigger 100 incidents
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/3] Triggering 100 incidents through the full agent pipeline...")
print("  Each: Detection → Step Functions → Bedrock AI → DynamoDB → Jira → SNS")
print("")

SERVICES = [
    'payments-api', 'orders-service', 'inventory-api', 'user-auth',
    'search-service', 'cart-service', 'shipping-api', 'notifications-svc',
    'analytics-engine', 'gateway-api', 'billing-service', 'catalog-api',
    'recommendations-svc', 'email-service', 'sms-gateway', 'webhook-processor',
    'image-service', 'video-transcoder', 'chat-service', 'audit-logger',
    'rate-limiter', 'cache-manager', 'queue-processor', 'scheduler-service',
    'config-service', 'secrets-manager', 'health-checker', 'load-balancer',
    'cdn-origin', 'database-proxy', 'redis-cluster', 'elasticsearch-svc',
    'kafka-consumer', 'event-bus', 'workflow-engine', 'ml-inference',
    'fraud-detection', 'compliance-checker', 'data-pipeline', 'etl-service',
    'report-generator', 'dashboard-api', 'admin-portal', 'mobile-backend',
    'iot-gateway', 'telemetry-collector', 'log-aggregator', 'metric-store',
    'alert-manager', 'incident-router', 'runbook-executor', 'backup-service',
    'disaster-recovery', 'dns-resolver', 'certificate-manager', 'vpn-gateway',
    'firewall-manager', 'waf-service', 'ddos-protection', 'api-throttler'
]

ALARM_SCENARIOS = [
    ('HighLatency', 'Threshold Crossed: P99 latency ({val}ms) > threshold (500ms)'),
    ('High5xxRate', 'Threshold Crossed: 5xx error count ({val}) > threshold (10)'),
    ('HighErrorRate', 'Threshold Crossed: error rate ({val}%) > threshold (5%)'),
    ('DBConnExhaustion', 'Threshold Crossed: active connections ({val}) > max pool size (100)'),
    ('HighCPU', 'Threshold Crossed: CPU utilization ({val}%) > threshold (85%)'),
    ('MemoryPressure', 'Threshold Crossed: memory usage ({val}%) > threshold (90%)'),
    ('HealthCheckFailing', '{val} consecutive health check failures detected'),
    ('QueueDepth', 'Threshold Crossed: queue depth ({val}) > threshold (1000)'),
    ('DiskUsage', 'Threshold Crossed: disk usage ({val}%) > threshold (85%)'),
    ('ResponseTimeout', 'Threshold Crossed: timeout count ({val}) > threshold (20)'),
    ('TLSCertExpiry', 'Certificate expires in {val} hours'),
    ('ReplicaLag', 'Threshold Crossed: replica lag ({val}s) > threshold (10s)'),
    ('ConnectionRefused', '{val} connection refused errors in last 5 minutes'),
    ('OOMKilled', '{val} OOM kill events in last 10 minutes'),
    ('ThrottlingRate', 'Threshold Crossed: throttled requests ({val}) > threshold (50)'),
]

triggered = 0
failed = 0

for i in range(100):
    service = SERVICES[i % len(SERVICES)]
    alarm_type, reason_template = ALARM_SCENARIOS[i % len(ALARM_SCENARIOS)]
    val = random.randint(50, 999)
    reason = reason_template.format(val=val)

    alarm_event = {
        'source': 'aws.cloudwatch',
        'detail-type': 'CloudWatch Alarm State Change',
        'detail': {
            'alarmName': f'{alarm_type}-{service}',
            'state': {
                'value': 'ALARM',
                'reason': reason
            },
            'previousState': {'value': 'OK'}
        }
    }

    try:
        response = lambda_client.invoke(
            FunctionName='outageshield-detection-dev',
            InvocationType='Event',
            Payload=json.dumps(alarm_event)
        )
        triggered += 1
        status = "✓"
    except Exception as e:
        failed += 1
        status = "✗"

    print(f"  [{i+1:3d}/100] {status} {alarm_type}-{service}")

    # Pause every 10 to avoid Step Functions throttling
    if (i + 1) % 10 == 0:
        print(f"        ... pausing 15s (batch {(i+1)//10}/10 complete)")
        time.sleep(15)
    else:
        time.sleep(1)

print("")
print("=" * 70)
print(f"  ✅ DONE")
print(f"     • DynamoDB: All tables cleared")
print(f"     • Jira: All tickets deleted")
print(f"     • Incidents: {triggered} triggered, {failed} failed")
print("")
print("  Wait ~15-20 minutes for Bedrock AI analysis to complete.")
print("  Dashboard: https://d2k1km1tzlio49.cloudfront.net")
print("=" * 70)
print("")
