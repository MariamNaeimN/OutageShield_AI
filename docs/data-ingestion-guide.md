# OutageShield AI — Data Ingestion Guide

## How Data Gets Into the System

OutageShield AI uses a **push-based** ingestion model. AWS services emit events automatically — you just need to route them to your Ingestion Lambda.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HOW DATA FLOWS IN                                  │
│                                                                     │
│  AWS Services emit events automatically                             │
│         │                                                           │
│         ▼                                                           │
│  EventBridge catches them via rules                                 │
│         │                                                           │
│         ▼                                                           │
│  Ingestion Lambda normalizes + stores                               │
│         │                                                           │
│         ▼                                                           │
│  DynamoDB (events table) + Detection Engine                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. CloudWatch Alarms (Automatic — Push)

**How:** CloudWatch alarms automatically emit state change events to EventBridge. No setup beyond creating the alarm.

```
CloudWatch Alarm triggers
       │
       ▼ (automatic)
EventBridge default bus receives:
  source: "aws.cloudwatch"
  detail-type: "CloudWatch Alarm State Change"
       │
       ▼ (your rule matches it)
Ingestion Lambda
```

**EventBridge Rule (already in your 01-ingestion-stack.yaml):**
```json
{
  "source": ["aws.cloudwatch"],
  "detail-type": ["CloudWatch Alarm State Change"]
}
```

**Sample event your Lambda receives:**
```json
{
  "source": "aws.cloudwatch",
  "detail-type": "CloudWatch Alarm State Change",
  "detail": {
    "alarmName": "HighLatency-PaymentAPI",
    "state": {
      "value": "ALARM",
      "reason": "Threshold Crossed: 1 datapoint (523.0) > 500.0"
    },
    "previousState": {"value": "OK"},
    "configuration": {
      "metrics": [{"id": "m1", "metricStat": {"metric": {"name": "Latency", "namespace": "AWS/ApiGateway"}}}]
    }
  }
}
```

**You don't call any API.** Just create alarms on your services — events flow automatically.

---

## 2. CloudTrail Events (Automatic — Push)

**How:** CloudTrail logs every AWS API call. EventBridge receives them automatically.

```
Someone deploys code / changes config / modifies IAM
       │
       ▼ (automatic)
CloudTrail records the API call
       │
       ▼ (automatic)
EventBridge default bus receives it
       │
       ▼ (your rule)
Ingestion Lambda
```

**EventBridge Rule:**
```json
{
  "source": ["aws.cloudtrail"]
}
```

**Useful events to watch for:**
- `UpdateFunctionCode` — Lambda deployment
- `UpdateService` — ECS deployment
- `CreateDeployment` — CodeDeploy
- `PutBucketPolicy` — S3 config change
- `AuthorizeSecurityGroupIngress` — security group change

**Sample event:**
```json
{
  "source": "aws.cloudtrail",
  "detail-type": "AWS API Call via CloudTrail",
  "detail": {
    "eventSource": "lambda.amazonaws.com",
    "eventName": "UpdateFunctionCode20150331v2",
    "userIdentity": {"arn": "arn:aws:iam::123456789:user/deploy-bot"},
    "requestParameters": {"functionName": "payment-api-prod"},
    "eventTime": "2025-05-20T14:30:00Z"
  }
}
```

---

## 3. AWS Config Changes (Automatic — Push)

**How:** AWS Config detects configuration drift and emits change events.

```
Resource configuration changes (EC2, RDS, Lambda, etc.)
       │
       ▼ (automatic)
AWS Config records the change
       │
       ▼ (automatic)
EventBridge receives:
  source: "aws.config"
  detail-type: "Config Configuration Item Change"
       │
       ▼ (your rule)
Ingestion Lambda
```

**EventBridge Rule:**
```json
{
  "source": ["aws.config"],
  "detail-type": ["Config Configuration Item Change"]
}
```

**Sample event:**
```json
{
  "source": "aws.config",
  "detail-type": "Config Configuration Item Change",
  "detail": {
    "configurationItem": {
      "resourceType": "AWS::RDS::DBInstance",
      "resourceId": "prod-orders-db",
      "configuration": {"dBInstanceClass": "db.r5.2xlarge"},
      "configurationItemDiff": {
        "changedProperties": {
          "Configuration.DBInstanceClass": {
            "previousValue": "db.r5.xlarge",
            "updatedValue": "db.r5.2xlarge"
          }
        }
      }
    }
  }
}
```

---

## 4. X-Ray Traces (Pull — Lambda Polls)

**How:** X-Ray doesn't push to EventBridge. Your Ingestion Lambda polls it on a schedule.

```
Application instrumented with X-Ray SDK
       │
       ▼ (automatic)
X-Ray collects traces
       │
       ▼ (your Lambda polls every 60s)
Ingestion Lambda calls GetTraceSummaries API
       │
       ▼
Normalizes and stores
```

**Add a scheduled EventBridge rule to trigger polling:**
```json
{
  "schedule": "rate(1 minute)",
  "target": "IngestionLambda",
  "input": {"poll_source": "xray"}
}
```

**Lambda code to pull X-Ray data:**
```python
import boto3
from datetime import datetime, timezone, timedelta

xray = boto3.client('xray')

def poll_xray_traces():
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=1)

    response = xray.get_trace_summaries(
        StartTime=start_time,
        EndTime=end_time,
        Sampling=False,
        FilterExpression='responsetime > 0.5'  # traces > 500ms
    )

    traces = response.get('TraceSummaries', [])

    for trace in traces:
        event = {
            'event_id': trace['Id'],
            'timestamp': trace['ResponseTime'].isoformat() if hasattr(trace.get('ResponseTime', ''), 'isoformat') else str(trace.get('ResponseTime')),
            'source': 'aws.xray',
            'severity': classify_trace_severity(trace),
            'service': extract_service_from_trace(trace),
            'payload': {
                'duration': trace.get('Duration', 0),
                'response_time': trace.get('ResponseTime', 0),
                'has_fault': trace.get('HasFault', False),
                'has_error': trace.get('HasError', False),
                'has_throttle': trace.get('HasThrottle', False),
                'http_status': trace.get('Http', {}).get('HttpStatus', 200)
            }
        }
        store_event(event)

def classify_trace_severity(trace):
    if trace.get('HasFault'):
        return 'critical'
    elif trace.get('HasError'):
        return 'high'
    elif trace.get('Duration', 0) > 2.0:
        return 'medium'
    return 'low'

def extract_service_from_trace(trace):
    # First entry point in the trace
    entry = trace.get('EntryPoint', {})
    return entry.get('Name', 'unknown')
```

---

## 5. CloudWatch Logs (Pull — Subscription Filter)

**How:** Use a CloudWatch Logs subscription filter to push matching log lines to your Lambda in real-time.

```
Application writes to CloudWatch Logs
       │
       ▼ (automatic via subscription filter)
Matching log events pushed to Ingestion Lambda
       │
       ▼
Normalize and store
```

**Create subscription filter (add to your ingestion stack):**
```yaml
LogSubscriptionFilter:
  Type: AWS::Logs::SubscriptionFilter
  Properties:
    LogGroupName: /aws/lambda/payment-api-prod
    FilterPattern: "?ERROR ?FATAL ?Exception ?Timeout ?OutOfMemory"
    DestinationArn: !GetAtt IngestionLambda.Arn
```

**Lambda receives log events in this format:**
```python
import base64
import gzip
import json

def handle_log_event(event, context):
    # CloudWatch Logs sends base64 + gzipped data
    payload = base64.b64decode(event['awslogs']['data'])
    log_data = json.loads(gzip.decompress(payload))

    for log_event in log_data['logEvents']:
        normalized = {
            'event_id': log_event['id'],
            'timestamp': log_event['timestamp'],
            'source': 'aws.cloudwatch.logs',
            'severity': classify_log_severity(log_event['message']),
            'service': log_data['logGroup'].split('/')[-1],
            'payload': {'message': log_event['message']}
        }
        store_event(normalized)

def classify_log_severity(message):
    if 'FATAL' in message or 'OutOfMemory' in message:
        return 'critical'
    elif 'ERROR' in message or 'Exception' in message:
        return 'high'
    elif 'WARN' in message or 'Timeout' in message:
        return 'medium'
    return 'informational'
```

---

## 6. CloudWatch Metrics (Pull — Lambda Polls)

**How:** For proactive anomaly detection beyond alarms, poll specific metrics on a schedule.

```python
import boto3
from datetime import datetime, timezone, timedelta

cloudwatch = boto3.client('cloudwatch')

def poll_metrics():
    """Poll key metrics every 60 seconds for anomaly detection."""

    metrics_to_watch = [
        {'Namespace': 'AWS/ApiGateway', 'MetricName': 'Latency', 'Dimensions': [{'Name': 'ApiName', 'Value': 'PaymentAPI'}]},
        {'Namespace': 'AWS/Lambda', 'MetricName': 'Errors', 'Dimensions': [{'Name': 'FunctionName', 'Value': 'payment-processor'}]},
        {'Namespace': 'AWS/RDS', 'MetricName': 'DatabaseConnections', 'Dimensions': [{'Name': 'DBInstanceIdentifier', 'Value': 'prod-orders-db'}]},
    ]

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)

    for metric in metrics_to_watch:
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[{
                'Id': 'm1',
                'MetricStat': {
                    'Metric': metric,
                    'Period': 60,
                    'Stat': 'Average'
                }
            }],
            StartTime=start_time,
            EndTime=end_time
        )

        values = response['MetricDataResults'][0].get('Values', [])
        if values:
            event = {
                'source': 'aws.cloudwatch.metrics',
                'service': metric['Dimensions'][0]['Value'],
                'payload': {
                    'metric_name': metric['MetricName'],
                    'namespace': metric['Namespace'],
                    'value': values[0],
                    'period': 60
                }
            }
            store_event(event)
```

---

## Summary: Push vs Pull

| Source | Method | Trigger | Latency |
|--------|--------|---------|---------|
| CloudWatch Alarms | **Push** (EventBridge) | Automatic on state change | < 10s |
| CloudTrail | **Push** (EventBridge) | Automatic on API call | < 5 min |
| AWS Config | **Push** (EventBridge) | Automatic on config change | < 5 min |
| CloudWatch Logs | **Push** (Subscription Filter) | Automatic on matching log line | < 5s |
| X-Ray Traces | **Pull** (scheduled Lambda) | Every 60 seconds | < 60s |
| CloudWatch Metrics | **Pull** (scheduled Lambda) | Every 60 seconds | < 60s |

---

## Quick Setup Checklist

1. ✅ Deploy `01-ingestion-stack.yaml` — creates EventBridge rules + Lambda
2. ✅ Create CloudWatch alarms on your services — events flow automatically
3. ✅ Enable CloudTrail (usually already on) — events flow automatically
4. ✅ Enable AWS Config — events flow automatically
5. ➕ Add subscription filters on your log groups for error patterns
6. ➕ Add scheduled rule (rate 1 min) for X-Ray polling
7. ➕ Add scheduled rule (rate 1 min) for metric polling

Steps 1-4 give you the core pipeline. Steps 5-7 add deeper visibility.
