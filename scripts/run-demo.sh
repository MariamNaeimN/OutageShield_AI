#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OutageShield AI — Demo Runner
# Pushes test events into EventBridge, then cleans up after.
#
# Usage:
#   ./run-demo.sh push          # Push all test events
#   ./run-demo.sh push 4        # Push only scenario 4 (full outage)
#   ./run-demo.sh cleanup       # Remove all test data after demo
# ─────────────────────────────────────────────────────────────────────────────

set -e

ACTION=${1:-push}
SCENARIO=${2:-all}
REGION=${AWS_REGION:-us-east-1}
EVENT_BUS=${EVENT_BUS:-default}
EVENTS_FILE="$(dirname "$0")/demo-test-events.json"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       OutageShield AI — Demo Test Data                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Action:    ${ACTION}"
echo "  Scenario:  ${SCENARIO}"
echo "  Region:    ${REGION}"
echo "  Event Bus: ${EVENT_BUS}"
echo ""

push_event() {
    local source="$1"
    local detail_type="$2"
    local detail="$3"
    local event_id="$4"

    aws events put-events \
        --region "${REGION}" \
        --entries "[{
            \"Source\": \"${source}\",
            \"DetailType\": \"${detail_type}\",
            \"Detail\": $(echo "$detail" | jq -c '.' | jq -Rs '.'),
            \"EventBusName\": \"${EVENT_BUS}\"
        }]" > /dev/null 2>&1

    echo "    ✓ ${event_id}: ${detail_type}"
}

push_scenario() {
    local scenario_key="$1"
    local description=$(jq -r ".${scenario_key}.description" "$EVENTS_FILE")
    local count=$(jq ".${scenario_key}.events | length" "$EVENTS_FILE")

    echo "  ──────────────────────────────────────────────────────────"
    echo "  ${description}"
    echo "  (${count} events)"
    echo ""

    for i in $(seq 0 $((count - 1))); do
        local source=$(jq -r ".${scenario_key}.events[$i].source" "$EVENTS_FILE")
        local detail_type=$(jq -r ".${scenario_key}.events[$i].detail_type" "$EVENTS_FILE")
        local detail=$(jq -c ".${scenario_key}.events[$i].detail" "$EVENTS_FILE")
        local event_id=$(jq -r ".${scenario_key}.events[$i].id" "$EVENTS_FILE")

        push_event "$source" "$detail_type" "$detail" "$event_id"
        sleep 0.5
    done
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# PUSH
# ─────────────────────────────────────────────────────────────────────────────
if [ "$ACTION" = "push" ]; then
    echo "  Pushing test events to EventBridge..."
    echo ""

    if [ "$SCENARIO" = "all" ] || [ "$SCENARIO" = "1" ]; then
        push_scenario "scenario_1_latency_spike"
    fi
    if [ "$SCENARIO" = "all" ] || [ "$SCENARIO" = "2" ]; then
        push_scenario "scenario_2_deployment_failure"
    fi
    if [ "$SCENARIO" = "all" ] || [ "$SCENARIO" = "3" ]; then
        push_scenario "scenario_3_config_drift"
    fi
    if [ "$SCENARIO" = "all" ] || [ "$SCENARIO" = "4" ]; then
        push_scenario "scenario_4_full_outage"
    fi

    echo "  ══════════════════════════════════════════════════════════"
    echo "  ✅ Test events pushed! Check:"
    echo "     • EventBridge → Ingestion Lambda logs"
    echo "     • DynamoDB events table"
    echo "     • Step Functions executions"
    echo "     • Dashboard"
    echo ""
    echo "  To clean up after demo:"
    echo "     ./run-demo.sh cleanup"
    echo "  ══════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────
elif [ "$ACTION" = "cleanup" ]; then
    echo "  🧹 Cleaning up demo test data..."
    echo ""

    # Delete test events from DynamoDB
    echo "  [1/3] Removing test events from DynamoDB..."
    EVENTS_TABLE="outageshield-events-dev"
    INCIDENTS_TABLE="outageshield-incidents-dev"

    # Scan and delete events with demo prefix
    aws dynamodb scan \
        --table-name "${EVENTS_TABLE}" \
        --region "${REGION}" \
        --filter-expression "begins_with(event_id, :prefix)" \
        --expression-attribute-values '{":prefix":{"S":"evt-demo"}}' \
        --projection-expression "event_id" \
        --output json 2>/dev/null | \
    jq -r '.Items[].event_id.S' 2>/dev/null | \
    while read -r id; do
        aws dynamodb delete-item \
            --table-name "${EVENTS_TABLE}" \
            --region "${REGION}" \
            --key "{\"event_id\":{\"S\":\"${id}\"}}" 2>/dev/null
        echo "    ✓ Deleted event: ${id}"
    done || echo "    (no test events found or table doesn't exist)"

    # Delete test incidents
    echo "  [2/3] Removing test incidents from DynamoDB..."
    aws dynamodb scan \
        --table-name "${INCIDENTS_TABLE}" \
        --region "${REGION}" \
        --projection-expression "incident_id" \
        --output json 2>/dev/null | \
    jq -r '.Items[].incident_id.S' 2>/dev/null | \
    while read -r id; do
        aws dynamodb delete-item \
            --table-name "${INCIDENTS_TABLE}" \
            --region "${REGION}" \
            --key "{\"incident_id\":{\"S\":\"${id}\"}}" 2>/dev/null
        echo "    ✓ Deleted incident: ${id}"
    done || echo "    (no test incidents found or table doesn't exist)"

    # Delete demo CloudWatch metrics
    echo "  [3/3] Removing demo CloudWatch alarms..."
    aws cloudwatch delete-alarms \
        --region "${REGION}" \
        --alarm-names \
            "HighLatency-payment-api" \
            "HighErrorRate-order-service" \
            "DBConnectionExhaustion-inventory-api" \
            "High5xxRate-payment-api" \
            "HealthCheckFailing-payment-api" \
        2>/dev/null || echo "    (alarms not found)"
    echo "    ✓ Demo alarms removed"

    echo ""
    echo "  ══════════════════════════════════════════════════════════"
    echo "  ✅ Cleanup complete! All demo data removed."
    echo "  ══════════════════════════════════════════════════════════"

else
    echo "  Usage:"
    echo "    ./run-demo.sh push          # Push all test scenarios"
    echo "    ./run-demo.sh push 4        # Push scenario 4 only"
    echo "    ./run-demo.sh cleanup       # Remove all test data"
fi

echo ""
