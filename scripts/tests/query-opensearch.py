"""Query OpenSearch to show stored data."""
import boto3
import json

# Get OpenSearch endpoint from Lambda config
lambda_client = boto3.client('lambda', region_name='us-east-1')
config = lambda_client.get_function_configuration(FunctionName='outageshield-detection-dev')
env_vars = config.get('Environment', {}).get('Variables', {})
endpoint = env_vars.get('OPENSEARCH_ENDPOINT', '')

print('OpenSearch Endpoint:', endpoint)

if not endpoint:
    print('No OpenSearch endpoint configured')
    exit(0)

# Query OpenSearch
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

host = endpoint.replace('https://', '')
credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, 'us-east-1', 'aoss')

client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

# Get all documents
print('\n' + '='*60)
print('OPENSEARCH DATA - outageshield-logs index')
print('='*60)

response = client.search(
    index='outageshield-logs',
    body={
        'query': {'match_all': {}},
        'size': 20,
        'sort': [{'timestamp': {'order': 'desc'}}]
    }
)

hits = response['hits']['hits']
total = response['hits']['total']['value']
print(f'\nTotal documents: {total}')
print(f'Showing: {len(hits)} most recent\n')

for i, hit in enumerate(hits, 1):
    doc = hit['_source']
    print(f'{i}. {doc.get("incident_id", "N/A")}')
    print(f'   Service: {doc.get("service", "N/A")}')
    print(f'   Alarm: {doc.get("alarm_name", "N/A")}')
    print(f'   Severity: {doc.get("severity", "N/A")}')
    print(f'   Type: {doc.get("detection_type", "N/A")}')
    print(f'   Timestamp: {doc.get("timestamp", "N/A")}')
    reason = doc.get('reason', '')
    if len(reason) > 80:
        print(f'   Reason: {reason[:80]}...')
    else:
        print(f'   Reason: {reason}')
    print()
