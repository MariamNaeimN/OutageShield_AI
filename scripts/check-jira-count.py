import boto3, json, urllib.request, urllib.parse, base64
sm = boto3.client('secretsmanager', region_name='us-east-1')
secret = sm.get_secret_value(SecretId='outageshield/jira-credentials')
creds = json.loads(secret['SecretString'])
auth = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
jql = urllib.parse.quote("project=TGSHLD ORDER BY created DESC")
url = f"{creds['jira_url']}/rest/api/3/search/jql?jql={jql}&maxResults=1&fields=key,description"
req = urllib.request.Request(url)
req.add_header('Authorization', f'Basic {auth}')
req.add_header('Accept', 'application/json')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())
print(f"Total tickets: {data.get('total', 0)}")
issues = data.get('issues', [])
if issues:
    print(f"Latest: {issues[0]['key']}")
    desc = issues[0].get('fields', {}).get('description', {})
    # Check if description contains dashboard link
    desc_str = json.dumps(desc)
    if 'cloudfront' in desc_str or 'Dashboard' in desc_str:
        print("✓ Dashboard link FOUND in ticket description")
    else:
        print("✗ Dashboard link NOT found in ticket description")
        print(f"  Description preview: {desc_str[:500]}")
