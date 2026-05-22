"""Check if data exists in OpenSearch Serverless."""
import boto3
import json
import urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import botocore.session

# Get OpenSearch endpoint from CloudFormation
cf = boto3.client('cloudformation', region_name='us-east-1')
outputs = cf.describe_stacks(StackName='outageshield-storage-dev')['Stacks'][0]['Outputs']
endpoint = None
for o in outputs:
    if 'OpenSearchEndpoint' in o.get('OutputKey', ''):
        endpoint = o['OutputValue']
        break

if not endpoint:
    print("OpenSearch endpoint not found in stack outputs")
    exit()

print(f"OpenSearch Endpoint: {endpoint}")

# Sign request with SigV4
session = botocore.session.get_session()
credentials = session.get_credentials().get_frozen_credentials()

# 1. List indices
print("\n--- Listing Indices ---")
try:
    url = f"{endpoint}/_cat/indices?format=json"
    request = AWSRequest(method='GET', url=url, headers={'Content-Type': 'application/json'})
    SigV4Auth(credentials, 'aoss', 'us-east-1').add_auth(request)
    
    req = urllib.request.Request(url, method='GET')
    for key, val in dict(request.headers).items():
        req.add_header(key, val)
    
    response = urllib.request.urlopen(req)
    indices = json.loads(response.read().decode())
    if indices:
        for idx in indices:
            print(f"  Index: {idx.get('index', '?')} | Docs: {idx.get('docs.count', '?')} | Size: {idx.get('store.size', '?')}")
    else:
        print("  No indices found (empty collection)")
except Exception as e:
    print(f"  Error: {e}")

# 2. Try searching
print("\n--- Searching all documents ---")
try:
    url = f"{endpoint}/_search"
    query = json.dumps({"query": {"match_all": {}}, "size": 3}).encode('utf-8')
    request = AWSRequest(method='POST', url=url, data=query, headers={'Content-Type': 'application/json'})
    SigV4Auth(credentials, 'aoss', 'us-east-1').add_auth(request)
    
    req = urllib.request.Request(url, data=query, method='POST')
    for key, val in dict(request.headers).items():
        req.add_header(key, val)
    
    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode())
    total = result.get('hits', {}).get('total', {}).get('value', 0)
    hits = result.get('hits', {}).get('hits', [])
    print(f"  Total documents: {total}")
    for hit in hits[:2]:
        print(f"  Sample: {json.dumps(hit.get('_source', {}), default=str)[:200]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n--- Done ---")
