"""Clear all data (keep runbooks) + push 100 incidents."""
import boto3, json, urllib.request, urllib.parse, base64, time, random

REGION = 'us-east-1'
print("=" * 60)
print("  OutageShield AI — Clear All + Push 100")
print("=" * 60)
print()

sm = boto3.client('secretsmanager', region_name=REGION)
try:
    print("[1/3] Deleting Jira tickets...")
    secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
    creds = json.loads(secret['SecretString'])
    auth_bytes = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    deleted = 0
    while True:
        jql = f"project={creds['project_key']} ORDER BY created DESC"
        url = f"{creds['jira_url']}/rest/api/3/search/jql?jql={urllib.parse.quote(jql)}&maxResults=50&fields=key"
        try:
            req = urllib.request.Request(url, method='GET')
            req.add_header('Authorization', f'Basic {auth_bytes}')
            req.add_header('Accept', 'application/json')
            data = json.loads(urllib.request.urlopen(req).read().decode())
            issues = data.get('issues', [])
            if not issues: break
            for issue in issues:
                try:
                    d_req = urllib.request.Request(f"{creds['jira_url']}/rest/api/3/issue/{issue['key']}?deleteSubtasks=true", method='DELETE')
                    d_req.add_header('Authorization', f'Basic {auth_bytes}')
                    urllib.request.urlopen(d_req)
                    deleted += 1
                except: pass
            time.sleep(1)
        except: break
    print(f"  Done: {deleted} tickets deleted")
except Exception as e:
    print(f"  Jira skipped: {e}")

print()
print("[2/3] Clearing DynamoDB (keeping runbooks)...")
dynamodb = boto3.resource('dynamodb', region_name=REGION)
for table_name in ['outageshield-incidents-dev', 'outageshield-events-dev', 'outageshield-workflow-state-dev', 'outageshield-postmortems-dev']:
    try:
        table = dynamodb.Table(table_name)
        key_names = [k['AttributeName'] for k in table.key_schema]
        count = 0
        scan_kwargs = {'ProjectionExpression': ', '.join(key_names)}
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            if not items: break
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={k: item[k] for k in key_names})
                    count += 1
            if 'LastEvaluatedKey' in response:
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            else: break
        print(f"  {table_name}: {count} deleted")
    except Exception as e:
        print(f"  {table_name}: {e}")

print()
print("[3/3] Pushing 100 incidents...")
lc = boto3.client('lambda', region_name=REGION)
SERVICES = ['payments-api','orders-service','inventory-api','user-auth','search-service','cart-service','shipping-api','notifications-svc','analytics-engine','gateway-api','billing-service','catalog-api','recommendations-svc','email-service','sms-gateway','webhook-processor','image-service','video-transcoder','chat-service','audit-logger','rate-limiter','cache-manager','queue-processor','scheduler-service','config-service','secrets-manager','health-checker','load-balancer','cdn-origin','database-proxy','redis-cluster','elasticsearch-svc','kafka-consumer','event-bus','workflow-engine','ml-inference','fraud-detection','compliance-checker','data-pipeline','etl-service','report-generator','dashboard-api','admin-portal','mobile-backend','iot-gateway','telemetry-collector','log-aggregator','metric-store','alert-manager','incident-router']
ALARMS = [('HighLatency','P99 latency ({val}ms) > 500ms'),('High5xxRate','5xx count ({val}) > 10'),('HighErrorRate','error rate ({val}%) > 5%'),('DBConnExhaustion','connections ({val}) > pool max (100)'),('HighCPU','CPU ({val}%) > 85%'),('MemoryPressure','memory ({val}%) > 90%'),('HealthCheckFailing','{val} health check failures'),('QueueDepth','queue depth ({val}) > 1000'),('DiskUsage','disk ({val}%) > 85%'),('ResponseTimeout','timeouts ({val}) > 20')]

triggered = 0
for i in range(100):
    service = SERVICES[i % len(SERVICES)]
    alarm_type, reason_tpl = ALARMS[i % len(ALARMS)]
    reason = f"Threshold Crossed: {reason_tpl.format(val=random.randint(50,999))}"
    try:
        lc.invoke(FunctionName='outageshield-detection-dev', InvocationType='Event', Payload=json.dumps({'source':'aws.cloudwatch','detail-type':'CloudWatch Alarm State Change','detail':{'alarmName':f'{alarm_type}-{service}','state':{'value':'ALARM','reason':reason},'previousState':{'value':'OK'}}}))
        triggered += 1
        if (i+1) % 20 == 0: print(f"  {i+1}/100 triggered")
    except: pass
    if (i+1) % 10 == 0: time.sleep(15)
    else: time.sleep(1)

print()
print("=" * 60)
print(f"  Done: {triggered}/100 triggered")
print(f"  Wait ~15-20 min for Bedrock AI to complete all workflows.")
print("=" * 60)
