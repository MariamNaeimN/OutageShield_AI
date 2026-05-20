"""
OutageShield AI — OpenSearch Serverless Index Setup

Run this AFTER the storage stack deploys to create the indexes
inside the OpenSearch Serverless collection.

Usage:
  python setup-opensearch-indexes.py

Indexes created:
  1. incident-contexts — stores correlated incident context documents
  2. incident-logs — stores raw log entries for pattern matching
  3. incident-signals — stores outage signals for trend analysis
"""

import boto3
import json
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = 'us-east-1'
COLLECTION_NAME = 'outageshield-dev'

# Get collection endpoint
aoss = boto3.client('opensearchserverless', region_name=REGION)

def get_collection_endpoint():
    """Get the OpenSearch Serverless collection endpoint."""
    response = aoss.batch_get_collection(names=[COLLECTION_NAME])
    collections = response.get('collectionDetails', [])
    if not collections:
        print(f"Collection '{COLLECTION_NAME}' not found. Deploy the storage stack first.")
        return None
    endpoint = collections[0].get('collectionEndpoint', '')
    print(f"Collection endpoint: {endpoint}")
    return endpoint


def create_client(endpoint):
    """Create an OpenSearch client with AWS SigV4 auth."""
    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        'aoss',
        session_token=credentials.token
    )

    host = endpoint.replace('https://', '')
    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30
    )
    return client


def create_indexes(client):
    """Create the indexes with proper mappings."""

    # ─────────────────────────────────────────────────────────────────────────
    # Index 1: incident-contexts
    # Stores the full correlated incident context for search
    # ─────────────────────────────────────────────────────────────────────────
    incident_contexts_mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        },
        "mappings": {
            "properties": {
                "context_id": {"type": "keyword"},
                "incident_id": {"type": "keyword"},
                "service": {"type": "keyword"},
                "severity_score": {"type": "integer"},
                "business_impact_score": {"type": "integer"},
                "status": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "root_cause": {"type": "text", "analyzer": "standard"},
                "confidence": {"type": "integer"},
                "deployments": {"type": "nested", "properties": {
                    "service": {"type": "keyword"},
                    "version": {"type": "keyword"},
                    "deployer": {"type": "keyword"},
                    "timestamp": {"type": "date"}
                }},
                "config_changes": {"type": "nested", "properties": {
                    "resource": {"type": "keyword"},
                    "property": {"type": "keyword"},
                    "old_value": {"type": "text"},
                    "new_value": {"type": "text"},
                    "timestamp": {"type": "date"}
                }},
                "recommendations": {"type": "nested", "properties": {
                    "category": {"type": "keyword"},
                    "description": {"type": "text"},
                    "effectiveness": {"type": "integer"},
                    "risk": {"type": "keyword"}
                }},
                "summary": {"type": "text", "analyzer": "standard"},
                "tags": {"type": "keyword"}
            }
        }
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Index 2: incident-logs
    # Stores raw log entries for full-text search and pattern matching
    # ─────────────────────────────────────────────────────────────────────────
    incident_logs_mapping = {
        "settings": {
            "index": {
                "number_of_shards": 2,
                "number_of_replicas": 0
            }
        },
        "mappings": {
            "properties": {
                "log_id": {"type": "keyword"},
                "incident_id": {"type": "keyword"},
                "service": {"type": "keyword"},
                "log_group": {"type": "keyword"},
                "level": {"type": "keyword"},
                "message": {"type": "text", "analyzer": "standard"},
                "timestamp": {"type": "date"},
                "request_id": {"type": "keyword"},
                "task_id": {"type": "keyword"}
            }
        }
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Index 3: incident-signals
    # Stores outage signals for trend analysis and pattern recognition
    # ─────────────────────────────────────────────────────────────────────────
    incident_signals_mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        },
        "mappings": {
            "properties": {
                "signal_id": {"type": "keyword"},
                "service": {"type": "keyword"},
                "detection_type": {"type": "keyword"},
                "severity_score": {"type": "integer"},
                "timestamp": {"type": "date"},
                "metric_name": {"type": "keyword"},
                "metric_value": {"type": "float"},
                "threshold": {"type": "float"},
                "consolidated": {"type": "boolean"},
                "consolidated_count": {"type": "integer"}
            }
        }
    }

    indexes = {
        "incident-contexts": incident_contexts_mapping,
        "incident-logs": incident_logs_mapping,
        "incident-signals": incident_signals_mapping
    }

    for index_name, mapping in indexes.items():
        try:
            if client.indices.exists(index=index_name):
                print(f"  ✓ Index '{index_name}' already exists")
            else:
                client.indices.create(index=index_name, body=mapping)
                print(f"  ✓ Index '{index_name}' created")
        except Exception as e:
            print(f"  ✗ Failed to create '{index_name}': {e}")


def main():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  OutageShield AI — OpenSearch Serverless Index Setup         ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    endpoint = get_collection_endpoint()
    if not endpoint:
        return

    print("\nWaiting for collection to be ACTIVE...")
    for i in range(30):
        response = aoss.batch_get_collection(names=[COLLECTION_NAME])
        status = response['collectionDetails'][0].get('status', '')
        if status == 'ACTIVE':
            print(f"  ✓ Collection is ACTIVE\n")
            break
        print(f"  ... status: {status} (attempt {i+1}/30)")
        time.sleep(10)
    else:
        print("  ✗ Collection did not become ACTIVE in time")
        return

    print("Creating indexes...")
    client = create_client(endpoint)
    create_indexes(client)

    print("\n──────────────────────────────────────────────────────────────")
    print("  ✅ OpenSearch Serverless setup complete!")
    print("  Indexes: incident-contexts, incident-logs, incident-signals")
    print("──────────────────────────────────────────────────────────────\n")


if __name__ == '__main__':
    main()
