"""
Delete ALL Jira tickets in the TGSHLD project.
"""
import boto3
import json
import urllib.request
import urllib.parse
import base64
import time

REGION = 'us-east-1'
sm = boto3.client('secretsmanager', region_name=REGION)

# Get Jira credentials
print("Loading Jira credentials...")
secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
creds = json.loads(secret['SecretString'])
JIRA_URL = creds['jira_url']
PROJECT_KEY = creds['project_key']
JIRA_EMAIL = creds['email']
JIRA_TOKEN = creds['api_token']
auth_bytes = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()

print(f"Connected to: {JIRA_URL} | Project: {PROJECT_KEY}")
print(f"Auth email: {JIRA_EMAIL}")
print("Searching for all tickets...")

# First, test connectivity with a simple API call
test_url = f"{JIRA_URL}/rest/api/3/myself"
print(f"  Testing API: {test_url}")
try:
    test_req = urllib.request.Request(test_url)
    test_req.add_header('Authorization', f'Basic {auth_bytes}')
    test_req.add_header('Accept', 'application/json')
    test_resp = urllib.request.urlopen(test_req)
    me = json.loads(test_resp.read().decode())
    print(f"  ✓ Connected as: {me.get('displayName', me.get('emailAddress', 'unknown'))}")
except urllib.error.HTTPError as e:
    body = e.read().decode() if e.fp else ''
    print(f"  ✗ API test failed: {e.code} {e.reason}")
    print(f"    Body: {body[:300]}")
except Exception as e:
    print(f"  ✗ API test failed: {e}")

deleted_count = 0
errors = 0

while True:
    # Use GET-based search with /rest/api/3/search/jql (Jira Cloud 2024+)
    jql = f"project={PROJECT_KEY} ORDER BY created DESC"
    search_url = f"{JIRA_URL}/rest/api/3/search/jql?jql={urllib.parse.quote(jql)}&maxResults=50&fields=key"

    try:
        req = urllib.request.Request(search_url, method='GET')
        req.add_header('Authorization', f'Basic {auth_bytes}')
        req.add_header('Accept', 'application/json')
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode())
        issues = data.get('issues', [])
        total = data.get('total', 0)

        if not issues:
            print(f"\nNo more tickets found. Done!")
            break

        print(f"\nFound {total} remaining tickets. Deleting batch of {len(issues)}...")

        for issue in issues:
            issue_key = issue['key']
            try:
                del_url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}?deleteSubtasks=true"
                del_req = urllib.request.Request(del_url, method='DELETE')
                del_req.add_header('Authorization', f'Basic {auth_bytes}')
                urllib.request.urlopen(del_req)
                deleted_count += 1
                print(f"  ✓ Deleted {issue_key} ({deleted_count} total)")
            except Exception as e:
                errors += 1
                print(f"  ✗ Failed {issue_key}: {e}")

        time.sleep(1)  # Rate limit between batches

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ''
        print(f"Search error: {e.code} {e.reason}")
        print(f"  URL: {search_url}")
        print(f"  Response: {body[:300]}")
        break
    except Exception as e:
        print(f"Search error: {e}")
        break

print(f"\n{'='*50}")
print(f"  ✅ Deleted {deleted_count} tickets ({errors} errors)")
print(f"{'='*50}")
