"""Create a completely fresh OpenSearch Serverless setup with a new name."""
import boto3
import json
import time

REGION = 'us-east-1'
ACCOUNT_ID = '193786182229'
COLLECTION_NAME = 'outageshield-logs-dev'  # New name to avoid any stale state

aoss = boto3.client('opensearchserverless', region_name=REGION)

# 1. Clean up old policies
print("[1/5] Cleaning up old policies...")
for policy_type in ['data']:
    policies = aoss.list_access_policies(type=policy_type)
    for p in policies.get('accessPolicySummaries', []):
        if 'outageshield' in p['name']:
            try:
                aoss.delete_access_policy(name=p['name'], type=policy_type)
                print(f"  Deleted data policy: {p['name']}")
            except: pass

for policy_type in ['encryption', 'network']:
    policies = aoss.list_security_policies(type=policy_type)
    for p in policies.get('securityPolicySummaries', []):
        if 'outageshield' in p['name']:
            try:
                aoss.delete_security_policy(name=p['name'], type=policy_type)
                print(f"  Deleted {policy_type} policy: {p['name']}")
            except: pass

# Wait for old collection to delete
print("\n[2/5] Waiting for old collection to delete...")
time.sleep(30)

# 2. Create encryption policy FIRST
print("\n[3/5] Creating policies...")
print("  Encryption policy...")
aoss.create_security_policy(
    name=f'{COLLECTION_NAME}-enc',
    type='encryption',
    policy=json.dumps({
        "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}],
        "AWSOwnedKey": True
    })
)

print("  Network policy...")
aoss.create_security_policy(
    name=f'{COLLECTION_NAME}-net',
    type='network',
    policy=json.dumps([{
        "Rules": [
            {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]},
            {"ResourceType": "dashboard", "Resource": [f"collection/{COLLECTION_NAME}"]}
        ],
        "AllowFromPublic": True
    }])
)

print("  Data access policy...")
aoss.create_access_policy(
    name=f'{COLLECTION_NAME}-access',
    type='data',
    policy=json.dumps([{
        "Rules": [
            {
                "ResourceType": "collection",
                "Resource": [f"collection/{COLLECTION_NAME}"],
                "Permission": ["aoss:CreateCollectionItems", "aoss:UpdateCollectionItems", "aoss:DescribeCollectionItems", "aoss:DeleteCollectionItems"]
            },
            {
                "ResourceType": "index",
                "Resource": [f"index/{COLLECTION_NAME}/*"],
                "Permission": ["aoss:CreateIndex", "aoss:UpdateIndex", "aoss:DescribeIndex", "aoss:DeleteIndex", "aoss:ReadDocument", "aoss:WriteDocument"]
            }
        ],
        "Principal": [
            f"arn:aws:iam::{ACCOUNT_ID}:user/mariam",
            f"arn:aws:iam::{ACCOUNT_ID}:role/outageshield-detection-role-dev",
            f"arn:aws:iam::{ACCOUNT_ID}:role/outageshield-agent-action-role-dev",
            f"arn:aws:iam::{ACCOUNT_ID}:role/outageshield-correlation-role-dev",
            f"arn:aws:iam::{ACCOUNT_ID}:role/outageshield-rootcause-role-dev",
            f"arn:aws:iam::{ACCOUNT_ID}:role/outageshield-investigator-agent-role-dev"
        ]
    }]),
    description='Full access for OutageShield AI'
)
print("  ✓ All policies created")

# 3. Create collection
print("\n[4/5] Creating collection...")
r = aoss.create_collection(name=COLLECTION_NAME, type='SEARCH', description='OutageShield AI log search')
collection_id = r['createCollectionDetail']['id']
print(f"  Collection ID: {collection_id}")
print("  Waiting for ACTIVE status...")

while True:
    detail = aoss.batch_get_collection(ids=[collection_id])
    status = detail['collectionDetails'][0]['status']
    endpoint = detail['collectionDetails'][0].get('collectionEndpoint', '')
    if status == 'ACTIVE':
        print(f"  ✓ ACTIVE! Endpoint: {endpoint}")
        break
    print(f"  Status: {status} (waiting 15s...)")
    time.sleep(15)

# 4. Wait for policy propagation and create index
print("\n[5/5] Creating index (waiting for policy propagation)...")
import urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import botocore.session

session = botocore.session.get_session()
creds = session.get_credentials().get_frozen_credentials()

for attempt in range(40):  # Up to 20 minutes
    try:
        url = f"{endpoint}/outageshield-logs"
        body = json.dumps({"mappings": {"properties": {
            "event_id": {"type": "keyword"},
            "service": {"type": "keyword"},
            "detection_type": {"type": "keyword"},
            "severity": {"type": "integer"},
            "alarm_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "reason": {"type": "text"},
            "source": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "message": {"type": "text"}
        }}}).encode()
        req = AWSRequest(method='PUT', url=url, data=body, headers={'Content-Type': 'application/json'})
        SigV4Auth(creds, 'aoss', REGION).add_auth(req)
        r = urllib.request.Request(url, data=body, method='PUT')
        for k, v in dict(req.headers).items():
            r.add_header(k, v)
        resp = urllib.request.urlopen(r)
        print(f"  ✓ Index 'outageshield-logs' created on attempt {attempt+1}!")
        
        # Update Lambda env vars with new endpoint
        lc = boto3.client('lambda', region_name=REGION)
        for fn in ['outageshield-detection-dev', 'outageshield-agent-actions-dev']:
            config = lc.get_function_configuration(FunctionName=fn)
            env = config['Environment']['Variables']
            env['OPENSEARCH_ENDPOINT'] = endpoint
            lc.update_function_configuration(FunctionName=fn, Environment={'Variables': env})
            print(f"  ✓ Updated {fn} endpoint")
        
        print(f"\n✅ OpenSearch ready! Endpoint: {endpoint}")
        break
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"  Attempt {attempt+1}: 403 (waiting 30s...)")
            time.sleep(30)
        else:
            body_text = e.read().decode() if e.fp else ''
            if 'already_exists' in body_text.lower():
                print(f"  ✓ Index already exists!")
                break
            print(f"  Attempt {attempt+1}: {e.code} - {body_text[:100]}")
            time.sleep(10)
else:
    print("\n⚠️ Policy still propagating. Run this script again in a few minutes.")
