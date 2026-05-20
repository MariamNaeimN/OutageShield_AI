"""
OutageShield AI — Approval Lambda

This Lambda handles the human-in-the-loop approval pattern:

1. SEND MODE (invoked by Step Functions with task token):
   - Stores the task token in DynamoDB
   - Sends approval request to the designated approver
   - Starts a 10-minute escalation timer (EventBridge scheduled rule)
   - Does NOT return — Step Functions waits for callback

2. RESPOND MODE (invoked by API Gateway when human approves/rejects):
   - Retrieves the stored task token
   - Calls SendTaskSuccess (approved) or SendTaskFailure (rejected)
   - Step Functions resumes execution

3. ESCALATE MODE (invoked by EventBridge after 10-minute timeout):
   - Sends escalation to next-level approver
   - Sends reminder to original approver
   - Does NOT auto-approve — still waits for human response
"""

import json
import boto3
import os
import uuid
from datetime import datetime, timezone, timedelta

sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
events = boto3.client('events')
scheduler = boto3.client('scheduler')

APPROVALS_TABLE = os.environ.get('APPROVALS_TABLE', 'outageshield-approvals')
APPROVAL_TOPIC_ARN = os.environ.get('APPROVAL_TOPIC_ARN', '')
ESCALATION_TOPIC_ARN = os.environ.get('ESCALATION_TOPIC_ARN', '')
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://outageshield.example.com')
ESCALATION_MINUTES = int(os.environ.get('ESCALATION_MINUTES', '10'))


def lambda_handler(event, context):
    """
    Route to appropriate handler based on invocation mode.
    """
    mode = event.get('mode', 'send')

    if 'task_token' in event:
        # Invoked by Step Functions — send approval request and store token
        return handle_send_approval(event)
    elif event.get('mode') == 'respond':
        # Invoked by API Gateway — human responded
        return handle_approval_response(event)
    elif event.get('mode') == 'escalate':
        # Invoked by EventBridge scheduler — 10-minute timeout
        return handle_escalation(event)
    else:
        return {'statusCode': 400, 'body': 'Unknown mode'}


def handle_send_approval(event):
    """
    Store task token and send approval request.
    Step Functions PAUSES here — no return value resumes it.
    Only SendTaskSuccess/SendTaskFailure will resume.
    """
    task_token = event['task_token']
    incident_id = event['incident_id']
    service = event['service']
    proposed_action = event.get('proposed_action', {})
    risk_level = event.get('risk_level', 'medium')

    # Generate approval ID
    approval_id = str(uuid.uuid4())[:8]

    # Store token in DynamoDB for later retrieval
    table = dynamodb.Table(APPROVALS_TABLE)
    table.put_item(Item={
        'approval_id': approval_id,
        'incident_id': incident_id,
        'task_token': task_token,
        'service': service,
        'proposed_action': json.dumps(proposed_action),
        'risk_level': risk_level,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'escalated': False
    })

    # Send approval request notification
    approve_url = f"{DASHBOARD_URL}/approve/{approval_id}?decision=approved"
    reject_url = f"{DASHBOARD_URL}/approve/{approval_id}?decision=rejected"

    message = f"""REMEDIATION APPROVAL REQUIRED

Incident: {incident_id}
Service: {service}
Proposed Action: {json.dumps(proposed_action, indent=2)}
Risk Level: {risk_level}

APPROVE: {approve_url}
REJECT:  {reject_url}

This request will escalate to the next-level approver in {ESCALATION_MINUTES} minutes if no response.

Dashboard: {DASHBOARD_URL}/incidents/{incident_id}"""

    sns.publish(
        TopicArn=APPROVAL_TOPIC_ARN,
        Subject=f"[APPROVAL NEEDED] Remediation for {service}",
        Message=message
    )

    # Schedule escalation after 10 minutes
    schedule_escalation(approval_id, incident_id, service, ESCALATION_MINUTES)

    # DO NOT return a value to Step Functions — it waits for the callback
    print(f"Approval request sent. ID: {approval_id}, Token stored. Workflow paused.")


def handle_approval_response(event):
    """
    Human responded via API Gateway.
    Resume Step Functions with the decision.
    """
    approval_id = event['approval_id']
    decision = event['decision']  # "approved" or "rejected"
    responder = event.get('responder', 'unknown')

    # Retrieve task token
    table = dynamodb.Table(APPROVALS_TABLE)
    response = table.get_item(Key={'approval_id': approval_id})
    item = response.get('Item')

    if not item:
        return {'statusCode': 404, 'body': 'Approval request not found'}

    if item['status'] != 'pending':
        return {'statusCode': 409, 'body': f"Already {item['status']}"}

    task_token = item['task_token']

    # Update approval record
    table.update_item(
        Key={'approval_id': approval_id},
        UpdateExpression='SET #s = :status, responded_at = :ts, responder = :resp',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':status': decision,
            ':ts': datetime.now(timezone.utc).isoformat(),
            ':resp': responder
        }
    )

    # Cancel escalation timer
    cancel_escalation(approval_id)

    # Resume Step Functions
    if decision == 'approved':
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps({
                'decision': 'approved',
                'responder': responder,
                'responded_at': datetime.now(timezone.utc).isoformat()
            })
        )
    else:
        sfn.send_task_failure(
            taskToken=task_token,
            error='ApprovalRejected',
            cause=f'Rejected by {responder}'
        )

    return {
        'statusCode': 200,
        'body': json.dumps({'approval_id': approval_id, 'decision': decision})
    }


def handle_escalation(event):
    """
    10-minute timeout — escalate to next-level approver.
    Does NOT auto-approve. Workflow stays paused.
    """
    approval_id = event['approval_id']
    incident_id = event.get('incident_id', '')
    service = event.get('service', '')

    # Check if already responded
    table = dynamodb.Table(APPROVALS_TABLE)
    response = table.get_item(Key={'approval_id': approval_id})
    item = response.get('Item')

    if not item or item['status'] != 'pending':
        print(f"Approval {approval_id} already handled. Skipping escalation.")
        return

    # Mark as escalated
    table.update_item(
        Key={'approval_id': approval_id},
        UpdateExpression='SET escalated = :e, escalated_at = :ts',
        ExpressionAttributeValues={
            ':e': True,
            ':ts': datetime.now(timezone.utc).isoformat()
        }
    )

    # Send escalation to next-level approver
    approve_url = f"{DASHBOARD_URL}/approve/{approval_id}?decision=approved"
    reject_url = f"{DASHBOARD_URL}/approve/{approval_id}?decision=rejected"

    sns.publish(
        TopicArn=ESCALATION_TOPIC_ARN,
        Subject=f"[ESCALATED] No response on remediation approval for {service}",
        Message=f"""ESCALATION: Original approver did not respond within {ESCALATION_MINUTES} minutes.

Incident: {incident_id}
Service: {service}
Original request sent {ESCALATION_MINUTES} minutes ago.

APPROVE: {approve_url}
REJECT:  {reject_url}

Dashboard: {DASHBOARD_URL}/incidents/{incident_id}"""
    )

    # Send reminder to original approver
    sns.publish(
        TopicArn=APPROVAL_TOPIC_ARN,
        Subject=f"[REMINDER] Pending approval for {service} — escalated",
        Message=f"Your approval request for incident {incident_id} has been escalated. Please respond."
    )

    print(f"Escalation sent for approval {approval_id}")


def schedule_escalation(approval_id, incident_id, service, minutes):
    """
    Create an EventBridge Scheduler one-time schedule to trigger escalation.
    """
    try:
        schedule_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        scheduler.create_schedule(
            Name=f"outageshield-escalation-{approval_id}",
            ScheduleExpression=f"at({schedule_time.strftime('%Y-%m-%dT%H:%M:%S')})",
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': os.environ.get('SELF_FUNCTION_ARN', ''),
                'RoleArn': os.environ.get('SCHEDULER_ROLE_ARN', ''),
                'Input': json.dumps({
                    'mode': 'escalate',
                    'approval_id': approval_id,
                    'incident_id': incident_id,
                    'service': service
                })
            }
        )
    except Exception as e:
        print(f"Failed to schedule escalation: {e}")


def cancel_escalation(approval_id):
    """
    Cancel the escalation schedule when approval is received.
    """
    try:
        scheduler.delete_schedule(Name=f"outageshield-escalation-{approval_id}")
    except Exception as e:
        print(f"Failed to cancel escalation schedule: {e}")
