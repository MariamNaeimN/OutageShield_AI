"""Test the Summary Lambda for a specific incident."""
import boto3
import json
import sys

lambda_client = boto3.client('lambda', region_name='us-east-1')
ddb = boto3.resource('dynamodb', region_name='us-east-1')
incidents_table = ddb.Table('outageshield-incidents-dev')

# Get incident ID from command line or use default
inc_id = sys.argv[1] if len(sys.argv) > 1 else 'INC-C7E7E6CF'

print("=" * 70)
print(f"Testing Summary Lambda for Incident: {inc_id}")
print("=" * 70)

# Fetch incident data from DynamoDB
response = incidents_table.get_item(Key={'incident_id': inc_id})
item = response.get('Item', {})

if not item:
    print(f"❌ Incident {inc_id} not found in DynamoDB")
    exit(1)

print(f"\n📋 Incident Details:")
print(f"   Service: {item.get('service', 'unknown')}")
print(f"   Title: {item.get('title', 'N/A')}")
print(f"   Severity: {item.get('severity', 'N/A')}")
print(f"   Status: {item.get('status', 'N/A')}")
print(f"   Root Cause: {item.get('root_cause', 'N/A')[:100]}...")

# Parse existing data
root_causes = []
root_causes_raw = item.get('root_causes_raw', '')
if root_causes_raw:
    try:
        root_causes = json.loads(root_causes_raw) if isinstance(root_causes_raw, str) else root_causes_raw
    except:
        pass

if not root_causes and item.get('root_cause'):
    root_causes = [{'description': item.get('root_cause'), 'confidence': 90}]

recommendations = []
recommendations_raw = item.get('recommendations_raw', '')
if recommendations_raw:
    try:
        recommendations = json.loads(recommendations_raw) if isinstance(recommendations_raw, str) else recommendations_raw
    except:
        pass

investigation = item.get('agent_investigation', item.get('investigation', ''))

print(f"\n📊 Data Available:")
print(f"   Root Causes: {len(root_causes)}")
print(f"   Recommendations: {len(recommendations)}")
print(f"   Investigation Length: {len(investigation)} chars")

# Build the event payload for Summary Lambda
# This mimics what the Step Functions workflow would pass
event = {
    'signal': {
        'signal_id': inc_id,
        'service': item.get('service', 'unknown'),
        'alarm_name': item.get('title', ''),
        'timestamp': item.get('created_at', '')
    },
    'step1': {  # Correlation result
        'incident_context': {
            'incident_id': inc_id,
            'service': item.get('service', 'unknown'),
            'alarm_name': item.get('title', '')
        }
    },
    'step2': {  # Scoring result
        'severity_score': item.get('severity', 3),
        'business_impact_score': item.get('business_impact', 5)
    },
    'step3': {  # RCA result
        'root_causes': root_causes,
        'incident_context_id': inc_id
    },
    'step3b': {  # Agent investigation
        'investigation': investigation
    },
    'step4': {  # Remediation result
        'recommendations': recommendations
    }
}

print(f"\n🚀 Invoking Summary Lambda...")
print("-" * 70)

# Invoke the Summary Lambda
try:
    response = lambda_client.invoke(
        FunctionName='outageshield-remediation-summary-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(event)
    )
    
    result = json.loads(response['Payload'].read().decode('utf-8'))
    
    print(f"\n✅ Summary Lambda Response:")
    print(f"   Status Code: {result.get('statusCode', 'N/A')}")
    
    summary = result.get('summary', {})
    
    if summary:
        print(f"\n" + "=" * 70)
        print("📝 GENERATED SUMMARY")
        print("=" * 70)
        
        print(f"\n🔍 Investigation Summary:")
        print(f"   {summary.get('investigation_summary', 'N/A')}")
        
        print(f"\n🎯 Root Cause:")
        print(f"   {summary.get('root_cause', 'N/A')}")
        
        print(f"\n📊 Recommendation Breakdown:")
        breakdown = summary.get('recommendation_breakdown', {})
        print(f"   Scaling: {breakdown.get('scaling', 0)}")
        print(f"   Rollback: {breakdown.get('rollback', 0)}")
        print(f"   Configuration: {breakdown.get('configuration_change', 0)}")
        print(f"   Manual: {breakdown.get('manual_intervention', 0)}")
        
        print(f"\n⚡ Recommended Action:")
        action = summary.get('recommended_action', {})
        print(f"   Type: {action.get('type', 'N/A')}")
        print(f"   Description: {action.get('description', 'N/A')[:200]}")
        print(f"   Confidence: {action.get('confidence', 'N/A')}%")
        print(f"   Estimated TTR: {action.get('estimated_ttr_minutes', 'N/A')} minutes")
        print(f"   Risk: {action.get('risk', 'N/A')}")
        
        print(f"\n🤖 AI Summary:")
        print("-" * 70)
        ai_summary = summary.get('ai_summary', 'N/A')
        # Word wrap the AI summary for better readability
        import textwrap
        wrapped = textwrap.fill(ai_summary, width=70)
        print(wrapped)
        print("-" * 70)
        
        print(f"\n🛠️ Quick Actions:")
        quick_actions = summary.get('quick_actions', [])
        for i, action in enumerate(quick_actions[:5], 1):
            print(f"\n   {i}. {action.get('label', 'N/A')}")
            print(f"      $ {action.get('command', 'N/A')[:80]}...")
        
        print(f"\n📅 Generated At: {summary.get('generated_at', 'N/A')}")
        print(f"📈 Data Sources Analyzed: {summary.get('data_sources_analyzed', 'N/A')}")
        
        # Check if summary was stored in DynamoDB
        print(f"\n" + "=" * 70)
        print("🔄 Verifying DynamoDB Storage...")
        
        # Check incidents table
        verify_response = incidents_table.get_item(Key={'incident_id': inc_id})
        verify_item = verify_response.get('Item', {})
        
        if verify_item.get('remediation_summary'):
            print(f"   ✅ Summary stored in incidents table")
            print(f"   📅 Summary generated at: {verify_item.get('summary_generated_at', 'N/A')}")
        else:
            print(f"   ⚠️ Summary not found in incidents table")
        
        # Check AI reasoning table
        ai_table = ddb.Table('outageshield-ai-reasoning-dev')
        try:
            ai_response = ai_table.get_item(Key={'incident_id': inc_id})
            ai_item = ai_response.get('Item', {})
            if ai_item:
                print(f"   ✅ Summary stored in AI reasoning table")
            else:
                print(f"   ⚠️ Summary not found in AI reasoning table")
        except Exception as e:
            print(f"   ⚠️ Could not check AI reasoning table: {e}")
        
    else:
        print(f"\n⚠️ No summary in response")
        print(f"Full response: {json.dumps(result, indent=2, default=str)[:1000]}")

except Exception as e:
    print(f"\n❌ Error invoking Summary Lambda: {e}")
    import traceback
    traceback.print_exc()

print(f"\n" + "=" * 70)
print("Test Complete")
print("=" * 70)
