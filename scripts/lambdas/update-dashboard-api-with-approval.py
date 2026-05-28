"""
Update Dashboard API Lambda with Human Approval Endpoint

This script:
1. Updates the dashboard API Lambda code
2. Adds IAM permissions for Step Functions and Approvals table
3. Adds the /approve/{approvalId} route to API Gateway
"""

import boto3
import json
import zipfile
import io
import os

lambda_client = boto3.client('lambda', region_name='us-east-1')
apigateway = boto3.client('apigateway', region_name='us-east-1')
iam = boto3.client('iam')

FUNCTION_NAME = 'outageshield-dashboard-api-dev'
API_NAME = 'outageshield-dashboard-dev'

# Read the updated code
script_dir = os.path.dirname(os.path.abspath(__file__))
code_path = os.path.join(script_dir, '..', '..', 'dashboard-api-code', 'index.py')

with open(code_path, 'r') as f:
    lambda_code = f.read()

print("=" * 60)
print("UPDATING DASHBOARD API WITH HUMAN APPROVAL")
print("=" * 60)

# Step 1: Update Lambda code
print("\n1. Updating Lambda code...")
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', lambda_code)
zip_buffer.seek(0)

try:
    response = lambda_client.update_function_code(
        FunctionName=FUNCTION_NAME,
        ZipFile=zip_buffer.read()
    )
    print(f"   ✅ Updated Lambda: {response['FunctionArn']}")
except Exception as e:
    print(f"   ❌ Failed to update Lambda: {e}")

# Step 2: Update Lambda environment variables
print("\n2. Updating environment variables...")
try:
    # Get current config
    current_config = lambda_client.get_function_configuration(FunctionName=FUNCTION_NAME)
    current_env = current_config.get('Environment', {}).get('Variables', {})
    
    # Add approvals table
    current_env['APPROVALS_TABLE'] = 'outageshield-approvals-dev'
    
    lambda_client.update_function_configuration(
        FunctionName=FUNCTION_NAME,
        Environment={'Variables': current_env}
    )
    print(f"   ✅ Added APPROVALS_TABLE environment variable")
except Exception as e:
    print(f"   ❌ Failed to update environment: {e}")

# Step 3: Add IAM permissions for Step Functions
print("\n3. Adding IAM permissions...")
try:
    # Get the Lambda's role
    func_config = lambda_client.get_function_configuration(FunctionName=FUNCTION_NAME)
    role_arn = func_config['Role']
    role_name = role_arn.split('/')[-1]
    
    # Add inline policy for Step Functions and Approvals table
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "states:SendTaskSuccess",
                    "states:SendTaskFailure"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem"
                ],
                "Resource": [
                    "arn:aws:dynamodb:us-east-1:*:table/outageshield-approvals-dev"
                ]
            }
        ]
    }
    
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName='ApprovalPermissions',
        PolicyDocument=json.dumps(policy_document)
    )
    print(f"   ✅ Added Step Functions and DynamoDB permissions to {role_name}")
except Exception as e:
    print(f"   ⚠️ IAM update: {e}")

# Step 4: Add /approve/{approvalId} route to API Gateway
print("\n4. Adding /approve/{approvalId} route to API Gateway...")
try:
    # Find the API
    apis = apigateway.get_rest_apis()
    api_id = None
    for api in apis['items']:
        if API_NAME in api['name'].lower() or 'outageshield' in api['name'].lower():
            api_id = api['id']
            print(f"   Found API: {api['name']} ({api_id})")
            break
    
    if not api_id:
        print("   ⚠️ API Gateway not found. You may need to add the route manually.")
    else:
        # Get resources
        resources = apigateway.get_resources(restApiId=api_id, limit=500)
        
        # Find root resource
        root_id = None
        approve_resource_id = None
        approve_id_resource_id = None
        
        for resource in resources['items']:
            if resource['path'] == '/':
                root_id = resource['id']
            elif resource['path'] == '/approve':
                approve_resource_id = resource['id']
            elif resource['path'] == '/approve/{approvalId}':
                approve_id_resource_id = resource['id']
        
        # Create /approve resource if it doesn't exist
        if not approve_resource_id:
            result = apigateway.create_resource(
                restApiId=api_id,
                parentId=root_id,
                pathPart='approve'
            )
            approve_resource_id = result['id']
            print(f"   ✅ Created /approve resource")
        
        # Create /approve/{approvalId} resource if it doesn't exist
        if not approve_id_resource_id:
            result = apigateway.create_resource(
                restApiId=api_id,
                parentId=approve_resource_id,
                pathPart='{approvalId}'
            )
            approve_id_resource_id = result['id']
            print(f"   ✅ Created /approve/{{approvalId}} resource")
        
        # Get Lambda ARN
        lambda_arn = lambda_client.get_function(FunctionName=FUNCTION_NAME)['Configuration']['FunctionArn']
        
        # Add POST method
        try:
            apigateway.put_method(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='POST',
                authorizationType='NONE'
            )
            print(f"   ✅ Added POST method")
        except apigateway.exceptions.ConflictException:
            print(f"   ℹ️ POST method already exists")
        
        # Add Lambda integration
        try:
            apigateway.put_integration(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='POST',
                type='AWS_PROXY',
                integrationHttpMethod='POST',
                uri=f'arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{lambda_arn}/invocations'
            )
            print(f"   ✅ Added Lambda integration")
        except Exception as e:
            print(f"   ⚠️ Integration: {e}")
        
        # Add OPTIONS method for CORS
        try:
            apigateway.put_method(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='OPTIONS',
                authorizationType='NONE'
            )
            
            apigateway.put_integration(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='OPTIONS',
                type='MOCK',
                requestTemplates={'application/json': '{"statusCode": 200}'}
            )
            
            apigateway.put_method_response(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': False,
                    'method.response.header.Access-Control-Allow-Methods': False,
                    'method.response.header.Access-Control-Allow-Origin': False
                }
            )
            
            apigateway.put_integration_response(
                restApiId=api_id,
                resourceId=approve_id_resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization'",
                    'method.response.header.Access-Control-Allow-Methods': "'GET,POST,OPTIONS'",
                    'method.response.header.Access-Control-Allow-Origin': "'*'"
                }
            )
            print(f"   ✅ Added OPTIONS method for CORS")
        except apigateway.exceptions.ConflictException:
            print(f"   ℹ️ OPTIONS method already exists")
        
        # Deploy API
        apigateway.create_deployment(
            restApiId=api_id,
            stageName='dev',
            description='Added /approve/{approvalId} endpoint for human approval'
        )
        print(f"   ✅ Deployed API to 'dev' stage")
        
        # Add Lambda permission for API Gateway
        try:
            account_id = boto3.client('sts').get_caller_identity()['Account']
            lambda_client.add_permission(
                FunctionName=FUNCTION_NAME,
                StatementId=f'apigateway-approve-{api_id}',
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=f'arn:aws:execute-api:us-east-1:{account_id}:{api_id}/*/POST/approve/*'
            )
            print(f"   ✅ Added API Gateway invoke permission")
        except lambda_client.exceptions.ResourceConflictException:
            print(f"   ℹ️ Permission already exists")

except Exception as e:
    print(f"   ❌ API Gateway error: {e}")

print("\n" + "=" * 60)
print("DONE!")
print("=" * 60)
print("""
Human Approval Flow:

1. Step Functions reaches WaitForHumanApproval state
2. Approval Lambda stores task token, sets incident to "Awaiting Approval"
3. Dashboard shows incident with Approve/Reject buttons
4. User clicks Approve → POST /approve/{incidentId} with {"decision": "approved"}
5. Dashboard API retrieves task token, calls SendTaskSuccess
6. Step Functions resumes execution

Test the endpoint:
  curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev/approve/INC-TEST001 \\
    -H "Content-Type: application/json" \\
    -d '{"decision": "approved", "responder": "test-user"}'
""")
