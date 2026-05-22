"""
Seed the outageshield-runbooks-dev table with remediation runbooks.
These are used by the Bedrock Agent when investigating incidents.
"""
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('outageshield-runbooks-dev')

RUNBOOKS = [
    {
        'runbook_id': 'HighLatency',
        'alarm_type': 'HighLatency',
        'title': 'High Latency Runbook',
        'description': 'Steps to diagnose and resolve high P99 latency issues',
        'steps': [
            'Check recent deployments for the affected service',
            'Review database connection pool utilization',
            'Check downstream dependency health and response times',
            'Consider rollback if latency started after a deployment',
            'Scale horizontally if the issue is load-related',
            'Check for network saturation or DNS resolution delays'
        ],
        'category': 'rollback',
        'estimated_ttr': '15 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'High5xxRate',
        'alarm_type': 'High5xxRate',
        'title': '5xx Error Rate Runbook',
        'description': 'Steps to diagnose and resolve elevated 5xx error rates',
        'steps': [
            'Check application logs for stack traces and error messages',
            'Verify database connectivity and query performance',
            'Check memory and CPU utilization on service instances',
            'Review recent configuration changes',
            'Rollback last deployment if errors started after deploy',
            'Check for expired certificates or secrets'
        ],
        'category': 'rollback',
        'estimated_ttr': '20 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'HighErrorRate',
        'alarm_type': 'HighErrorRate',
        'title': 'High Error Rate Runbook',
        'description': 'Steps to diagnose and resolve elevated application error rates',
        'steps': [
            'Identify the specific error types from application logs',
            'Check if errors correlate with a specific endpoint or operation',
            'Verify external dependency availability (APIs, databases, caches)',
            'Check for resource exhaustion (threads, connections, file descriptors)',
            'Review recent code changes that may have introduced bugs',
            'Enable debug logging temporarily for deeper investigation'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '25 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'HighCPU',
        'alarm_type': 'HighCPU',
        'title': 'High CPU Utilization Runbook',
        'description': 'Steps to diagnose and resolve high CPU usage',
        'steps': [
            'Identify hot threads or processes consuming CPU',
            'Check for infinite loops or runaway processes',
            'Look for memory leaks causing excessive garbage collection',
            'Scale up instance size or add replicas',
            'Review recent code changes for performance regressions',
            'Enable CPU profiling for detailed root cause analysis'
        ],
        'category': 'scaling',
        'estimated_ttr': '10 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'MemoryPressure',
        'alarm_type': 'MemoryPressure',
        'title': 'Memory Pressure Runbook',
        'description': 'Steps to diagnose and resolve high memory usage or OOM conditions',
        'steps': [
            'Check for memory leaks in the application (growing heap over time)',
            'Review heap dump if available',
            'Restart affected instances to reclaim memory immediately',
            'Scale up memory allocation (instance type or container limits)',
            'Check for cache overflow or unbounded data structures',
            'Review recent changes that may have increased memory footprint'
        ],
        'category': 'scaling',
        'estimated_ttr': '10 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'DBConnExhaustion',
        'alarm_type': 'DBConnExhaustion',
        'title': 'Database Connection Exhaustion Runbook',
        'description': 'Steps to diagnose and resolve database connection pool exhaustion',
        'steps': [
            'Check for connection leaks in application code (unclosed connections)',
            'Increase connection pool size in application configuration',
            'Add connection timeout and idle timeout settings',
            'Check for long-running queries holding connections',
            'Consider read replicas for read-heavy workloads',
            'Review connection pool metrics over time for trends'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '15 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'HealthCheckFailing',
        'alarm_type': 'HealthCheckFailing',
        'title': 'Health Check Failure Runbook',
        'description': 'Steps to diagnose and resolve failing health checks',
        'steps': [
            'Check if the service process is running on the instance',
            'Verify the health check endpoint is responding locally',
            'Check for port conflicts or binding issues',
            'Review application startup logs for errors',
            'Check if dependencies required for health check are available',
            'Restart the service and monitor recovery'
        ],
        'category': 'manual_intervention',
        'estimated_ttr': '5 minutes',
        'severity_threshold': 5
    },
    {
        'runbook_id': 'QueueDepth',
        'alarm_type': 'QueueDepth',
        'title': 'Queue Depth Runbook',
        'description': 'Steps to diagnose and resolve growing message queue depth',
        'steps': [
            'Check consumer health — are consumers running and processing?',
            'Look for poison messages causing consumer failures',
            'Scale up consumer count to increase throughput',
            'Check for downstream bottlenecks slowing processing',
            'Review dead letter queue for failed messages',
            'Consider temporarily increasing consumer batch size'
        ],
        'category': 'scaling',
        'estimated_ttr': '15 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'DiskUsage',
        'alarm_type': 'DiskUsage',
        'title': 'Disk Usage Runbook',
        'description': 'Steps to diagnose and resolve high disk utilization',
        'steps': [
            'Identify largest files and directories consuming disk space',
            'Check for log files that need rotation or cleanup',
            'Look for temp files or core dumps accumulating',
            'Expand volume size if legitimate data growth',
            'Enable log rotation and set retention policies',
            'Move large data to S3 or EFS if appropriate'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '10 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'ResponseTimeout',
        'alarm_type': 'ResponseTimeout',
        'title': 'Response Timeout Runbook',
        'description': 'Steps to diagnose and resolve request timeouts',
        'steps': [
            'Check downstream service response times',
            'Look for network connectivity issues between services',
            'Check for thread pool exhaustion in the application',
            'Review timeout configuration values',
            'Add circuit breakers to prevent cascade failures',
            'Scale the slow downstream service if it is the bottleneck'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '20 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'TLSCertExpiry',
        'alarm_type': 'TLSCertExpiry',
        'title': 'TLS Certificate Expiry Runbook',
        'description': 'Steps to resolve expiring or expired TLS certificates',
        'steps': [
            'Identify which certificate is expiring and its domain',
            'Check if auto-renewal is configured (ACM, Let\'s Encrypt)',
            'Manually renew the certificate if auto-renewal failed',
            'Deploy the new certificate to load balancers/CDN',
            'Verify the new certificate is serving correctly',
            'Set up monitoring alerts for future certificate expirations'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '30 minutes',
        'severity_threshold': 2
    },
    {
        'runbook_id': 'ReplicaLag',
        'alarm_type': 'ReplicaLag',
        'title': 'Database Replica Lag Runbook',
        'description': 'Steps to diagnose and resolve database replication lag',
        'steps': [
            'Check write volume on the primary — is it unusually high?',
            'Look for long-running transactions blocking replication',
            'Check replica instance CPU and I/O utilization',
            'Consider upgrading replica instance size',
            'Check network throughput between primary and replica',
            'If lag is critical, failover to a healthy replica'
        ],
        'category': 'scaling',
        'estimated_ttr': '20 minutes',
        'severity_threshold': 3
    },
    {
        'runbook_id': 'ConnectionRefused',
        'alarm_type': 'ConnectionRefused',
        'title': 'Connection Refused Runbook',
        'description': 'Steps to diagnose and resolve connection refused errors',
        'steps': [
            'Verify the target service is running and listening on the expected port',
            'Check security groups and network ACLs for blocked traffic',
            'Look for service crashes or OOM kills in logs',
            'Check if the service hit its max connection limit',
            'Restart the service if it is in a bad state',
            'Check DNS resolution — is the hostname resolving correctly?'
        ],
        'category': 'manual_intervention',
        'estimated_ttr': '10 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'OOMKilled',
        'alarm_type': 'OOMKilled',
        'title': 'OOM Kill Runbook',
        'description': 'Steps to diagnose and resolve Out of Memory kill events',
        'steps': [
            'Check which process was OOM killed and its memory usage pattern',
            'Review application memory limits (container, JVM heap, etc.)',
            'Look for memory leaks — is usage growing over time?',
            'Increase memory limits for the container or instance',
            'Add memory-based autoscaling to prevent future OOMs',
            'Review recent code changes for memory-intensive operations'
        ],
        'category': 'scaling',
        'estimated_ttr': '10 minutes',
        'severity_threshold': 4
    },
    {
        'runbook_id': 'ThrottlingRate',
        'alarm_type': 'ThrottlingRate',
        'title': 'Throttling Rate Runbook',
        'description': 'Steps to diagnose and resolve API throttling',
        'steps': [
            'Identify which API or service is being throttled',
            'Check if the throttling is from AWS service limits (DynamoDB, Lambda, etc.)',
            'Request a service limit increase if hitting AWS quotas',
            'Implement exponential backoff and retry in the calling service',
            'Add caching to reduce the number of API calls',
            'Consider request batching to stay within rate limits'
        ],
        'category': 'configuration_change',
        'estimated_ttr': '15 minutes',
        'severity_threshold': 3
    }
]

print(f"Seeding {len(RUNBOOKS)} runbooks into outageshield-runbooks-dev...")

for runbook in RUNBOOKS:
    runbook['created_at'] = datetime.now(timezone.utc).isoformat()
    table.put_item(Item=runbook)
    print(f"  ✓ {runbook['runbook_id']}: {runbook['title']}")

print(f"\n✅ Done. {len(RUNBOOKS)} runbooks seeded.")
