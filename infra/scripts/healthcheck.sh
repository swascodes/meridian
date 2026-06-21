#!/bin/bash
# Health check script for all Meridian services

set -e

SERVICES=(
    "API:http://localhost:8000/health"
    "Graph Engine:http://localhost:8001/health"
    "Route Optimizer:http://localhost:8002/health"
    "Quality Oracle:http://localhost:8003/health"
    "Predictive Engine:http://localhost:8004/health"
    "Ingestion:http://localhost:8005/health"
)

echo "═══════════════════════════════════════"
echo "  Meridian Health Check"
echo "═══════════════════════════════════════"

all_healthy=true

for service_url in "${SERVICES[@]}"; do
    name="${service_url%%:http*}"
    url="http${service_url#*:http}"

    if status=$(curl -sf "$url" 2>/dev/null | jq -r '.status' 2>/dev/null); then
        if [ "$status" = "healthy" ]; then
            echo "  ✓ $name: $status"
        else
            echo "  ✗ $name: $status"
            all_healthy=false
        fi
    else
        echo "  ✗ $name: unreachable"
        all_healthy=false
    fi
done

echo "═══════════════════════════════════════"

if $all_healthy; then
    echo "  All services healthy ✓"
    exit 0
else
    echo "  Some services unhealthy ✗"
    exit 1
fi
