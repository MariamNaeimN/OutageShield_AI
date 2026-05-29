import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')

def lambda_handler(event, context):
    """
    Dashboard API: Serves data for the Incident Command Dashboard.
    Routes: /incidents, /incidents/{id}, /risk, /postmortems, /events, /ai-reasoning/{id}, /approve/{id}
    """
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')

    # Handle CORS preflight
    if method == 'OPTIONS':
        return response(200, {})

    if path == '/incidents' and method == 'GET':
        return get_active_incidents()
    elif path.startswith('/incidents/') and method == 'GET':
        incident_id = path.split('/')[-1]
        return get_incident_detail(incident_id)
    elif path == '/risk' and method == 'GET':
        return get_risk_overview()
    elif path == '/postmortems' and method == 'GET':
        return get_postmortems()
    elif path == '/events' and method == 'GET':
        return get_events()
    elif path.startswith('/ai-reasoning/') and method == 'GET':
        incident_id = path.split('/')[-1]
        return get_ai_reasoning(incident_id)
    elif path.startswith('/approve/') and method == 'POST':
        approval_id = path.split('/')[-1]
        return handle_approval(approval_id, event)
    elif path == '/approval/callback' and method == 'POST':
        return handle_servicenow_callback(event)
    else:
        return response(404, {'error': 'Not found'})

def get_active_incidents():
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.scan(
        FilterExpression='#s <> :resolved',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':resolved': 'resolved'}
    )
    incidents = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(
            FilterExpression='#s <> :resolved',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':resolved': 'resolved'},
            ExclusiveStartKey=result['LastEvaluatedKey']
        )
        incidents.extend(result.get('Items', []))
    incidents = sorted(incidents, key=lambda x: int(x.get('severity_score', 0)), reverse=True)
    return response(200, {'incidents': incidents, 'count': len(incidents)})

def get_incident_detail(incident_id):
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.get_item(Key={'incident_id': incident_id})
    item = result.get('Item')
    if item:
        return response(200, item)
    return response(404, {'error': 'Incident not found'})

def get_risk_overview():
    """Aggregate real service_risk_score and revenue_at_risk from incidents (scored by Bedrock AI)."""
    table = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
    result = table.scan(
        ProjectionExpression='service, severity_score, service_risk_score, business_impact_score, revenue_at_risk, created_at'
    )
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(
            ProjectionExpression='service, severity_score, service_risk_score, business_impact_score, revenue_at_risk, created_at',
            ExclusiveStartKey=result['LastEvaluatedKey']
        )
        items.extend(result.get('Items', []))

    svc_map = {}
    for item in items:
        svc = item.get('service', 'unknown')
        if svc not in svc_map:
            svc_map[svc] = {'scores': [], 'severities': [], 'count': 0, 'last_incident': '', 'revenue_values': []}
        svc_map[svc]['count'] += 1
        svc_map[svc]['scores'].append(int(item.get('service_risk_score', 50)))
        svc_map[svc]['severities'].append(int(item.get('severity_score', 3)))
        # Parse revenue_at_risk (e.g. "$5,000/hour") to numeric
        rev_str = item.get('revenue_at_risk', '0')
        rev_num = parse_revenue(rev_str)
        svc_map[svc]['revenue_values'].append(rev_num)
        ts = item.get('created_at', '')
        if ts > svc_map[svc]['last_incident']:
            svc_map[svc]['last_incident'] = ts

    services = []
    for svc, data in svc_map.items():
        avg_risk = sum(data['scores']) / len(data['scores']) if data['scores'] else 50
        max_sev = max(data['severities']) if data['severities'] else 3
        total_revenue = sum(data['revenue_values'])
        if avg_risk >= 85:
            risk_level = 'Critical'
        elif avg_risk >= 80:
            risk_level = 'High'
        elif avg_risk >= 75:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'
        services.append({
            'service': svc,
            'risk': risk_level,
            'risk_score': int(avg_risk),
            'revenue_at_risk': total_revenue,
            'activeSignals': data['count'],
            'max_severity': max_sev,
            'lastIncident': data['last_incident']
        })

    services.sort(key=lambda x: x['revenue_at_risk'], reverse=True)
    return response(200, {'services': services, 'last_calculated': ''})

def parse_revenue(rev_str):
    """Parse '$5,000/hour' or '$10,000/hour' to integer."""
    if not rev_str or rev_str == 'Unknown':
        return 0
    import re
    nums = re.findall(r'[\d,]+', str(rev_str))
    if nums:
        return int(nums[0].replace(',', ''))
    return 0

def get_postmortems():
    table = dynamodb.Table(os.environ.get('POSTMORTEMS_TABLE', 'outageshield-postmortems-dev'))
    result = table.scan()
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'])
        items.extend(result.get('Items', []))
    return response(200, {'postmortems': items, 'count': len(items)})

def get_events():
    table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'outageshield-events-dev'))
    result = table.scan()
    items = result.get('Items', [])
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'])
        items.extend(result.get('Items', []))
    return response(200, {'events': items, 'count': len(items)})

def get_ai_reasoning(incident_id):
    """Get AI reasoning data for an incident from the ai-reasoning table."""
    table = dynamodb.Table(os.environ.get('AI_REASONING_TABLE', 'outageshield-ai-reasoning-dev'))
    # Table has composite key (incident_id, created_at), so we query by incident_id
    # and get the most recent entry
    result = table.query(
        KeyConditionExpression='incident_id = :iid',
        ExpressionAttributeValues={':iid': incident_id},
        ScanIndexForward=False,  # Sort descending by created_at
        Limit=1
    )
    items = result.get('Items', [])
    if items:
        item = items[0]
        # Parse JSON strings in the response
        if 'quick_actions' in item and isinstance(item['quick_actions'], str):
            try:
                item['quick_actions'] = json.loads(item['quick_actions'])
            except:
                pass
        if 'recommended_action' in item and isinstance(item['recommended_action'], str):
            try:
                item['recommended_action'] = json.loads(item['recommended_action'])
            except:
                pass
        if 'recommendation_breakdown' in item and isinstance(item['recommendation_breakdown'], str):
            try:
                item['recommendation_breakdown'] = json.loads(item['recommendation_breakdown'])
            except:
                pass
        return response(200, item)
    return response(404, {'error': 'AI reasoning not found for this incident'})

def handle_approval(approval_id, event):
    """
    Handle human approval/rejection from the dashboard.
    Retrieves task token from DynamoDB and resumes Step Functions.
    """
    from datetime import datetime, timezone
    
    print(f"handle_approval called for {approval_id}")
    
    # Parse request body
    body = event.get('body', '{}')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {}
    
    decision = body.get('decision', 'approved')
    responder = body.get('responder', 'dashboard-user')
    
    print(f"Decision: {decision}, Responder: {responder}")
    
    if decision not in ['approved', 'rejected']:
        return response(400, {'error': 'Invalid decision. Must be "approved" or "rejected"'})
    
    # Get task token from approvals table
    approvals_table = dynamodb.Table(os.environ.get('APPROVALS_TABLE', 'outageshield-approvals-dev'))
    incidents_table = dynamodb.Table(os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev'))
    
    try:
        result = approvals_table.get_item(Key={'approval_id': approval_id})
        item = result.get('Item')
    except Exception as e:
        print(f"DynamoDB error: {e}")
        return response(500, {'error': f'Database error: {str(e)}'})
    
    if not item:
        return response(404, {'error': f'Approval request {approval_id} not found'})
    
    task_token = item.get('task_token')
    incident_id = item.get('incident_id', approval_id)
    current_status = item.get('status', 'pending')
    
    print(f"Current approval status: {current_status}, incident_id: {incident_id}")
    
    # If already processed, still update the incident but don't try Step Functions again
    already_processed = current_status != 'pending'
    
    now = datetime.now(timezone.utc).isoformat()
    new_status = 'Approved' if decision == 'approved' else 'Rejected'
    
    # Always update approval record
    try:
        approvals_table.update_item(
            Key={'approval_id': approval_id},
            UpdateExpression='SET #s = :status, responded_at = :ts, responder = :resp, decision = :dec',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': decision,
                ':ts': now,
                ':resp': responder,
                ':dec': decision
            }
        )
        print(f"Updated approval {approval_id} to {decision}")
    except Exception as e:
        print(f"Failed to update approval: {e}")
    
    # Always update incident status
    try:
        incidents_table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET #s = :status, approval_decision = :dec, approved_by = :by, approved_at = :ts',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':dec': decision,
                ':by': responder,
                ':ts': now
            }
        )
        print(f"Updated incident {incident_id} status to {new_status}")
    except Exception as e:
        print(f"Failed to update incident status: {e}")
        # Return error if incident update fails
        return response(500, {'error': f'Failed to update incident: {str(e)}'})
    
    # Resume Step Functions only if not already processed
    if not already_processed and task_token:
        try:
            if decision == 'approved':
                sfn.send_task_success(
                    taskToken=task_token,
                    output=json.dumps({
                        'decision': 'approved',
                        'responder': responder,
                        'responded_at': now
                    })
                )
                print(f"Sent SendTaskSuccess for {approval_id}")
            else:
                sfn.send_task_failure(
                    taskToken=task_token,
                    error='ApprovalRejected',
                    cause=f'Rejected by {responder}'
                )
                print(f"Sent SendTaskFailure for {approval_id}")
        except Exception as e:
            print(f"Failed to resume Step Functions: {e}")
            # Don't fail - the approval and incident are already updated
    
    return response(200, {
        'success': True,
        'approvalId': approval_id,
        'incidentId': incident_id,
        'decision': decision,
        'newStatus': new_status,
        'responder': responder,
        'message': f'Remediation {decision}. Status updated to {new_status}.'
    })


def handle_servicenow_callback(event):
    """
    Handle callback from ServiceNow when a change request is approved/rejected.
    ServiceNow sends: incident_id, task_token, action (approve/reject), approved_by/rejected_by, change_number
    """
    from datetime import datetime, timezone
    
    print(f"ServiceNow callback received: {event}")
    
    # Parse request body
    body = event.get('body', '{}')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {}
    
    print(f"Parsed body: {body}")
    
    incident_id = body.get('incident_id')
    task_token = body.get('task_token')
    # ServiceNow sends 'action' as 'approve' or 'reject'
    action = body.get('action', body.get('decision', 'reject'))
    approver = body.get('approved_by') or body.get('rejected_by') or body.get('approver', 'servicenow-user')
    change_number = body.get('change_number', '')
    
    print(f"ServiceNow callback: incident={incident_id}, action={action}, approver={approver}, change={change_number}")
    
    if not incident_id:
        return response(400, {'error': 'Missing incident_id'})
    
    # Normalize decision
    if action.lower() in ['approved', 'approve', 'yes']:
        decision = 'approved'
    else:
        decision = 'rejected'
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Get task token from approvals table if not provided
    approvals_table = dynamodb.Table(os.environ.get('APPROVALS_TABLE', 'outageshield-approvals-dev'))
    
    if not task_token:
        try:
            # Try with incident_id as approval_id
            result = approvals_table.get_item(Key={'approval_id': incident_id})
            item = result.get('Item')
            if item:
                task_token = item.get('task_token')
                print(f"Found task token from approvals table")
            else:
                # Try scanning for incident_id
                scan_result = approvals_table.scan(
                    FilterExpression='incident_id = :iid',
                    ExpressionAttributeValues={':iid': incident_id}
                )
                if scan_result.get('Items'):
                    task_token = scan_result['Items'][0].get('task_token')
                    print(f"Found task token via scan")
        except Exception as e:
            print(f"Error getting task token: {e}")
    
    # Update approval record
    try:
        approvals_table.update_item(
            Key={'approval_id': incident_id},
            UpdateExpression='SET #s = :status, responded_at = :ts, responder = :resp, decision = :dec, servicenow_approved = :sn',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': decision,
                ':ts': now,
                ':resp': f'ServiceNow: {approver}',
                ':dec': decision,
                ':sn': True
            }
        )
        print(f"Updated approval {incident_id} to {decision}")
    except Exception as e:
        print(f"Failed to update approval: {e}")
    
    # Update incident status - THIS IS THE KEY PART
    try:
        incidents_table = dynamodb.Table(os.environ.get('INCIDENTS_TABLE', 'outageshield-incidents-dev'))
        new_status = 'Approved' if decision == 'approved' else 'Rejected'
        incidents_table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression='SET #s = :status, approval_decision = :dec, approved_by = :by, approved_at = :ts',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':dec': decision,
                ':by': f'ServiceNow: {approver}',
                ':ts': now
            }
        )
        print(f"Updated incident {incident_id} status to {new_status}")
    except Exception as e:
        print(f"Failed to update incident status: {e}")
    
    # Resume Step Functions if we have a task token
    if task_token:
        try:
            if decision == 'approved':
                sfn.send_task_success(
                    taskToken=task_token,
                    output=json.dumps({
                        'decision': 'approved',
                        'responder': f'ServiceNow: {approver}',
                        'responded_at': now,
                        'servicenow_change': change_number
                    })
                )
                print(f"Sent SendTaskSuccess for {incident_id}")
            else:
                sfn.send_task_failure(
                    taskToken=task_token,
                    error='ApprovalRejected',
                    cause=f'Rejected by ServiceNow: {approver}'
                )
                print(f"Sent SendTaskFailure for {incident_id}")
        except Exception as e:
            print(f"Failed to resume Step Functions: {e}")
            # Don't fail the callback - the approval is still recorded
    else:
        print(f"No task token found - incident status updated but workflow not resumed")
    
    return response(200, {
        'success': True,
        'incident_id': incident_id,
        'decision': decision,
        'new_status': 'Mitigating' if decision == 'approved' else 'Rejected',
        'approver': approver,
        'message': f'ServiceNow approval processed: {decision}'
    })


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
