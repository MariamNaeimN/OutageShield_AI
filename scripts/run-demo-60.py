"""
OutageShield AI — Full Demo: 60 Incidents
==========================================
NO CHEATING. Every single data point is produced by the agent pipeline:
  Detection Lambda → Step Functions → Bedrock AI → DynamoDB

This script:
1. Clears ALL tables (fresh start)
2. Generates 60 realistic CloudWatch alarm events
3. Sends each to the Detection Lambda
4. Detection Lambda stores event + starts Step Functions workflow
5. Workflow runs: Correlate → Score → RCA → Remediation → Ticket → Notify → Postmortem
6. All results stored in DynamoDB by the Lambdas (not this script)

Run: python scripts/run-demo-60.py
Wait: ~10-15 minutes for all Bedrock analysis to complete
Check: https://601lnlm7r5.execute-api.us-east-1.amazonaws.com/dev/incidents
"""

import boto3
import json
import time
import random

REGION = 'us-east-1'
lambda_client = boto3.client('lambda', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# ─────────────────────────────────────────────────────────────────────────────
# 60 realistic services and alarm scenarios
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Clear all tables
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  OutageShield AI — FULL DEMO (100 Incidents)")
print("  No cheating. All data produced by the AI agent pipeline.")
print("=" * 70)

print("\n[1/2] Clearing ALL tables (fresh start)...")
for table_name in ['outageshield-incidents-dev', 'outageshield-events-dev',
                   'outageshield-workflow-state-dev', 'outageshield-postmortems-dev']:
    table = dynamodb.Table(table_name)
    key_name = table.key_schema[0]['AttributeName']
    response = table.scan(ProjectionExpression=key_name)
    items = response.get('Items', [])
    for item in items:
        table.delete_item(Key={key_name: item[key_name]})
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ProjectionExpression=key_name, ExclusiveStartKey=response['LastEvaluatedKey'])
        for item in response.get('Items', []):
            table.delete_item(Key={key_name: item[key_name]})
        items.extend(response.get('Items', []))
    print(f"  ✓ Cleared {table_name} ({len(items)} items)")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Trigger 60 incidents
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[2/2] Triggering 100 incidents through the full agent pipeline...")
print("  Each incident runs: Detection → Events → Step Functions → Bedrock AI")
print("  → Correlation → Scoring → RCA → Remediation → Ticket → Notify → Postmortem")
print("")

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
            InvocationType='Event',  # Async
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
print(f"  ✅ {triggered} incidents triggered, {failed} failed")
print("")
print("  Workflows are running in parallel.")
print("  Wait ~15-20 minutes for all Bedrock AI analysis to complete.")
print("")
print("  Then check ALL tables:")
print(f"    • outageshield-events-dev       → {triggered} events")
print(f"    • outageshield-incidents-dev    → {triggered} incidents (with AI analysis)")
print(f"    • outageshield-workflow-state-dev → {triggered} workflow records")
print(f"    • outageshield-postmortems-dev  → {triggered} AI postmortems")
print("")
print("  Dashboard: https://d2k1km1tzlio49.cloudfront.net")
print("  UI: cd UI && npm run dev → http://localhost:3000")
print("=" * 70)
print("")
