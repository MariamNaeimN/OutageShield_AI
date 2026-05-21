"""
OutageShield AI — Clean Reset & Push Exactly 100
=================================================
1. Clears ALL DynamoDB tables
2. Deletes ALL Jira tickets
3. Waits for any running Step Functions to finish
4. Triggers exactly 100 incidents
"""
import boto3
import json
import time
import random
import urllib.request
import urllib.parse
import base64

REGION = 'us-east-1'
lambda_client = boto3.client('lambda', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sfn = boto3.client('stepfunctions', region_name=REGION)
sm = boto3.client('secretsmanager', region_name=REGION)

print("\n" + "=" * 70)
print("  OutageShield AI — CLEAN RESET & PUSH 100")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Stop any running Step Functions executions
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/4] Stopping any running Step Functions executions...")
try:
    sm_arn = None
    paginator = sfn.get_paginator('list_state_machines')
    for page in paginator.paginate():
        for machine in page['stateMachines']:
            if 'outageshield-workflow' in machine['name']:
                sm_arn = machine['stateMachineArn']
                break
        if sm_arn:
            break

    if sm_arn:
        running = sfn.list_executions(stateMachineArn=sm_arn, statusFilter='RUNNING', maxResults=100)
        executions = running.get('executions', [])
        print(f"  Found {len(executions)} running executions")
        for ex in executions:
            try:
                sfn.stop_execution(executionArn=ex['executionArn'], cause='Reset for clean demo')
            except:
                pass
        print(f"  ✓ Stopped {len(executions)} executions")
    else:
        print("  No state machine found")
except Exception as e:
    print(f"  ⚠ Could not stop executions: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Clear all DynamoDB tables
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Clearing ALL DynamoDB tables...")
for table_name in ['outageshield-incidents-dev', 'outageshield-events-dev',
                   'outageshield-workflow-state-dev', 'outageshield-postmortems-dev']:
    try:
        table = dynamodb.Table(table_name)
        key_name = table.key_schema[0]['AttributeName']
        count = 0
        response = table.scan(ProjectionExpression=key_name)
        items = response.get('Items', [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={key_name: item[key_name]})
                count += 1
        while 'LastEvaluatedKey' in response:
            response = table.scan(ProjectionExpression=key_name, ExclusiveStartKey=response['LastEvaluatedKey'])
            with table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={key_name: item[key_name]})
                    count += 1
        print(f"  ✓ Cleared {table_name} ({count} items)")
    except Exception as e:
        print(f"  ✗ {table_name}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Delete all Jira tickets
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Deleting ALL Jira tickets...")
try:
    secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
    creds = json.loads(secret['SecretString'])
    JIRA_URL = creds['jira_url']
    PROJECT_KEY = creds['project_key']
    auth_bytes = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()

    deleted = 0
    while True:
        jql = urllib.parse.quote(f"project={PROJECT_KEY} ORDER BY created DESC")
        url = f"{JIRA_URL}/rest/api/3/search/jql?jql={jql}&maxResults=50&fields=key"
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Basic {auth_bytes}')
        req.add_header('Accept', 'application/json')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read().decode())
        issues = data.get('issues', [])
        if not issues:
            break
        for issue in issues:
            try:
                del_url = f"{JIRA_URL}/rest/api/3/issue/{issue['key']}?deleteSubtasks=true"
                del_req = urllib.request.Request(del_url, method='DELETE')
                del_req.add_header('Authorization', f'Basic {auth_bytes}')
                urllib.request.urlopen(del_req)
                deleted += 1
            except:
                pass
        time.sleep(0.5)
    print(f"  ✓ Deleted {deleted} Jira tickets")
except Exception as e:
    print(f"  ⚠ Jira cleanup: {e}")

# Wait a moment for everything to settle
print("\n  Waiting 10s for cleanup to settle...")
time.sleep(10)

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Trigger exactly 100 incidents
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Triggering exactly 100 incidents...")

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
            'state': {'value': 'ALARM', 'reason': reason},
            'previousState': {'value': 'OK'}
        }
    }

    try:
        lambda_client.invoke(
            FunctionName='outageshield-detection-dev',
            InvocationType='Event',
            Payload=json.dumps(alarm_event)
        )
        triggered += 1
        print(f"  [{i+1:3d}/100] ✓ {alarm_type}-{service}")
    except Exception as e:
        failed += 1
        print(f"  [{i+1:3d}/100] ✗ {alarm_type}-{service}: {e}")

    if (i + 1) % 10 == 0:
        print(f"        ... pausing 15s (batch {(i+1)//10}/10)")
        time.sleep(15)
    else:
        time.sleep(1)

print(f"\n{'='*70}")
print(f"  ✅ DONE: {triggered} triggered, {failed} failed")
print(f"  Wait ~15-20 min for all Bedrock AI workflows to complete.")
print(f"  Dashboard: https://d2k1km1tzlio49.cloudfront.net")
print(f"  Jira: https://corpinfollc.atlassian.net/jira/software/projects/TGSHLD/boards/4495")
print(f"{'='*70}\n")
