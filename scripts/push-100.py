"""Push exactly 100 incidents (assumes tables are already clean)."""
import boto3, json, time, random

REGION = 'us-east-1'
lambda_client = boto3.client('lambda', region_name=REGION)

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

print("Pushing 100 incidents...")
triggered = 0
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
        lambda_client.invoke(FunctionName='outageshield-detection-dev', InvocationType='Event', Payload=json.dumps(alarm_event))
        triggered += 1
        print(f"  [{i+1:3d}/100] ✓ {alarm_type}-{service}")
    except Exception as e:
        print(f"  [{i+1:3d}/100] ✗ {e}")

    if (i + 1) % 10 == 0:
        print(f"        ... pausing 15s")
        time.sleep(15)
    else:
        time.sleep(1)

print(f"\n✅ Done: {triggered}/100 triggered")
print("Wait ~15-20 min for Bedrock AI to complete all workflows.")
