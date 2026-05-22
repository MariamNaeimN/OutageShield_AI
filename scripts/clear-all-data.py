"""Clear all DynamoDB tables + delete all Jira tickets."""
import boto3
import json
import urllib.request
import urllib.parse
import base64
import time

REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sm = boto3.client('secretsmanager', region_name=REGION)

print("=" * 50)
print("  CLEARING ALL DATA")
print("=" * 50)

# 1. Clear DynamoDB
print("\n[1/2] Clearing DynamoDB tables...")
for table_name in ['outageshield-incidents-dev', 'outageshield-events-dev',
                   'outageshield-workflow-state-dev', 'outageshield-postmortems-dev']:
    try:
        table = dynamodb.Table(table_name)
        key_name = table.key_schema[0]['AttributeName']
        count = 0
        response = table.scan(ProjectionExpression=key_name)
        with table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(Key={key_name: item[key_name]})
                count += 1
        while 'LastEvaluatedKey' in response:
            response = table.scan(ProjectionExpression=key_name, ExclusiveStartKey=response['LastEvaluatedKey'])
            with table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={key_name: item[key_name]})
                    count += 1
        print(f"  ✓ {table_name}: {count} items deleted")
    except Exception as e:
        print(f"  ✗ {table_name}: {e}")

# 2. Delete Jira tickets
print("\n[2/2] Deleting Jira tickets...")
try:
    secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
    creds = json.loads(secret['SecretString'])
    auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
    deleted = 0

    while True:
        jql = urllib.parse.quote(f"project={creds['project_key']} ORDER BY created DESC")
        url = f"{creds['jira_url']}/rest/api/3/search/jql?jql={jql}&maxResults=50&fields=key"
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Basic {auth}')
        req.add_header('Accept', 'application/json')
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read().decode())
        issues = data.get('issues', [])
        if not issues:
            break
        for issue in issues:
            try:
                del_url = f"{creds['jira_url']}/rest/api/3/issue/{issue['key']}?deleteSubtasks=true"
                del_req = urllib.request.Request(del_url, method='DELETE')
                del_req.add_header('Authorization', f'Basic {auth}')
                urllib.request.urlopen(del_req)
                deleted += 1
            except:
                pass
        time.sleep(0.5)
    print(f"  ✓ Deleted {deleted} Jira tickets")
except Exception as e:
    print(f"  ✗ Jira: {e}")

print(f"\n{'='*50}")
print("  ✅ ALL DATA CLEARED")
print(f"{'='*50}")
