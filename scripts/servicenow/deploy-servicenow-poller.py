"""
Deploy the ServiceNow Approval Poller Lambda with EventBridge trigger.
This Lambda polls ServiceNow every minute for approved change requests.
"""
import boto3
import json
import zipfile
import io
import os

LAMBDA_NAME = 'outageshield-servicenow-poller-dev'
REGION = 'us-east-1'
ACCOUNT_ID = '193786182229'

lambda_client = boto3.client('lambda', region_name=REGION)
events_client = boto3.client('events', region_name=REGION)
iam_client = boto3.client('iam', region_name=REGION)

# Lambda code
LAMBDA_CODE = '''
"""
ServiceNow Approval Poller Lambda

Polls ServiceNow for approved change requests and triggers Step Functions callbacks.
"""
import boto3
import json
import os
import urllib.request
import urllib.error
import base64
from datetime import datetime, timezone

sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

APPROVALS_TABLE = os.environ.get('APPROVALS_TABLE', 'outageshield-approvals-dev')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev')


def get_servicenow_credentials():
    """Get ServiceNow credentials from SSM Parameter Store."""
    try:
        instance = ssm.get_parameter(Name='/outageshield/servicenow/instance')['Parameter']['Value']
        username = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
        password = ssm.get_parameter(Name='/outageshield/servicenow/password', WithDecryption=True)['Parameter']['Value']
        return instance, username, password
    except Exception as e:
        print(f"Error getting SSM parameters: {e}")
        return 'dev252089.service-now.com', 'admin', ''


def make_sn_request(url, username, password):
    """Make authenticated request to ServiceNow."""
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        return None
    except Exception as e:
        print(f"Request error: {e}")
        return None


def lambda_handler(event, context):
    print("[Poller] Starting ServiceNow approval poll...")
    
    sn_instance, username, password = get_servicenow_credentials()
    
    table = dynamodb.Table(APPROVALS_TABLE)
    response = table.scan(
        FilterExpression='#s = :pending',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':pending': 'pending'}
    )
    
    pending_approvals = response.get('Items', [])
    print(f"[Poller] Found {len(pending_approvals)} pending approvals")
    
    if not pending_approvals:
        return {'processed': 0}
    
    incidents_table = dynamodb.Table(INCIDENTS_TABLE)
    processed = 0
    
    for approval in pending_approvals:
        approval_id = approval.get('approval_id', '')
        incident_id = approval.get('incident_id', '')
        task_token = approval.get('task_token', '')
        
        if not task_token or task_token.startswith('test-token'):
            continue
        
        try:
            inc_response = incidents_table.get_item(Key={'incident_id': incident_id})
            incident = inc_response.get('Item', {})
            sn_number = incident.get('servicenow_change', '') or incident.get('servicenow_number', '')
            
            if not sn_number:
                print(f"[Poller] No ServiceNow number for {incident_id}")
                continue
            
            sn_url = f"https://{sn_instance}/api/now/table/change_request?sysparm_query=number={sn_number}&sysparm_fields=number,state,approval,u_outageshield_approval_status&sysparm_limit=1"
            
            data = make_sn_request(sn_url, username, password)
            if not data:
                continue
            
            results = data.get('result', [])
            if not results:
                print(f"[Poller] Change request {sn_number} not found")
                continue
            
            change = results[0]
            state = change.get('state', '')
            approval_status = change.get('approval', '')
            os_approval = change.get('u_outageshield_approval_status', '').upper()
            
            print(f"[Poller] {sn_number}: state={state}, approval={approval_status}, os_approval={os_approval}")
            
            # Check approval status - also check our custom field
            is_approved = approval_status == 'approved' or state in ['-2', '-1', '0', '3'] or os_approval == 'APPROVED'
            is_rejected = approval_status == 'rejected' or state == '4' or os_approval == 'REJECTED'
            
            if is_approved:
                print(f"[Poller] ✅ {sn_number} APPROVED!")
                try:
                    sfn.send_task_success(
                        taskToken=task_token,
                        output=json.dumps({
                            'decision': 'approved',
                            'responder': 'servicenow-poller',
                            'servicenow_number': sn_number,
                            'responded_at': datetime.now(timezone.utc).isoformat()
                        })
                    )
                    
                    table.update_item(
                        Key={'approval_id': approval_id},
                        UpdateExpression='SET #s = :status, responded_at = :ts, responder = :by',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'approved',
                            ':ts': datetime.now(timezone.utc).isoformat(),
                            ':by': 'servicenow-poller'
                        }
                    )
                    
                    incidents_table.update_item(
                        Key={'incident_id': incident_id},
                        UpdateExpression='SET #s = :status, approved_at = :ts, approved_by = :by, approval_decision = :dec',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'Approved',
                            ':ts': datetime.now(timezone.utc).isoformat(),
                            ':by': 'servicenow-poller',
                            ':dec': 'approved'
                        }
                    )
                    
                    processed += 1
                    print(f"[Poller] ✅ Workflow resumed for {incident_id}")
                except Exception as e:
                    print(f"[Poller] Error: {e}")
                    
            elif is_rejected:
                print(f"[Poller] ❌ {sn_number} REJECTED!")
                try:
                    sfn.send_task_failure(
                        taskToken=task_token,
                        error='ApprovalRejected',
                        cause=f'Rejected in ServiceNow ({sn_number})'
                    )
                    
                    table.update_item(
                        Key={'approval_id': approval_id},
                        UpdateExpression='SET #s = :status, responded_at = :ts, responder = :by',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'rejected',
                            ':ts': datetime.now(timezone.utc).isoformat(),
                            ':by': 'servicenow-poller'
                        }
                    )
                    
                    incidents_table.update_item(
                        Key={'incident_id': incident_id},
                        UpdateExpression='SET #s = :status, rejected_at = :ts, rejected_by = :by, approval_decision = :dec',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'Rejected',
                            ':ts': datetime.now(timezone.utc).isoformat(),
                            ':by': 'servicenow-poller',
                            ':dec': 'rejected'
                        }
                    )
                    
                    processed += 1
                except Exception as e:
                    print(f"[Poller] Error: {e}")
                    
        except Exception as e:
            print(f"[Poller] Error processing {incident_id}: {e}")
    
    print(f"[Poller] Processed {processed} approvals")
    return {'processed': processed}
'''

def create_deployment_package():
    """Create a zip file with the Lambda code."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('index.py', LAMBDA_CODE)
    zip_buffer.seek(0)
    return zip_buffer.read()

def get_or_create_role():
    """Get or create the Lambda execution role."""
    role_name = 'outageshield-poller-role'
    role_arn = f'arn:aws:iam::{ACCOUNT_ID}:role/{role_name}'
    
    try:
        iam_client.get_role(RoleName=role_name)
        print(f"Using existing role: {role_name}")
        return role_arn
    except iam_client.exceptions.NoSuchEntityException:
        print(f"Creating role: {role_name}")
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for OutageShield ServiceNow Poller Lambda'
        )
        
        # Attach policies
        policies = [
            'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
            'arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess',
            'arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess',
            'arn:aws:iam::aws:policy/SecretsManagerReadWrite'
        ]
        
        for policy in policies:
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy)
        
        import time
        time.sleep(10)  # Wait for role to propagate
        
        return role_arn

def main():
    print("=" * 60)
    print("DEPLOYING SERVICENOW APPROVAL POLLER")
    print("=" * 60)
    
    # Get role
    role_arn = get_or_create_role()
    
    # Create deployment package
    print("\nCreating deployment package...")
    zip_bytes = create_deployment_package()
    
    # Check if Lambda exists
    try:
        lambda_client.get_function(FunctionName=LAMBDA_NAME)
        print(f"\nUpdating existing Lambda: {LAMBDA_NAME}")
        
        lambda_client.update_function_code(
            FunctionName=LAMBDA_NAME,
            ZipFile=zip_bytes
        )
        
        # Wait for code update to complete
        import time
        print("Waiting for code update to complete...")
        time.sleep(10)
        
        lambda_client.update_function_configuration(
            FunctionName=LAMBDA_NAME,
            Environment={
                'Variables': {
                    'APPROVALS_TABLE': 'outageshield-approvals-dev',
                    'INCIDENTS_TABLE': 'outageshield-incidents-dev'
                }
            },
            Timeout=60
        )
        
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"\nCreating new Lambda: {LAMBDA_NAME}")
        
        lambda_client.create_function(
            FunctionName=LAMBDA_NAME,
            Runtime='python3.11',
            Role=role_arn,
            Handler='index.lambda_handler',
            Code={'ZipFile': zip_bytes},
            Timeout=60,
            MemorySize=256,
            Environment={
                'Variables': {
                    'APPROVALS_TABLE': 'outageshield-approvals-dev',
                    'INCIDENTS_TABLE': 'outageshield-incidents-dev'
                }
            }
        )
    
    print(f"✅ Lambda deployed: {LAMBDA_NAME}")
    
    # Create EventBridge rule to trigger every minute
    rule_name = 'outageshield-poller-schedule'
    
    print(f"\nCreating EventBridge rule: {rule_name}")
    
    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression='rate(1 minute)',
        State='ENABLED',
        Description='Triggers ServiceNow approval poller every minute'
    )
    
    # Add Lambda permission for EventBridge
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_NAME,
            StatementId='EventBridgeInvoke',
            Action='lambda:InvokeFunction',
            Principal='events.amazonaws.com',
            SourceArn=f'arn:aws:events:{REGION}:{ACCOUNT_ID}:rule/{rule_name}'
        )
    except lambda_client.exceptions.ResourceConflictException:
        pass  # Permission already exists
    
    # Add Lambda as target
    events_client.put_targets(
        Rule=rule_name,
        Targets=[{
            'Id': 'servicenow-poller-target',
            'Arn': f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{LAMBDA_NAME}'
        }]
    )
    
    print(f"✅ EventBridge rule created: {rule_name}")
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 60)
    print(f"""
The poller will run every minute and:
1. Check all pending approvals in DynamoDB
2. Query ServiceNow for each change request status
3. If approved in ServiceNow → trigger Step Functions callback
4. If rejected in ServiceNow → trigger Step Functions failure

Now when you approve a change request in ServiceNow, the workflow
will automatically continue within 1 minute!
""")

if __name__ == '__main__':
    main()
