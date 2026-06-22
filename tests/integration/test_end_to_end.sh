#!/bin/bash
# test_end_to_end.sh
# Verifies route discovery edge cases against the local API gateway

API_URL="http://localhost:8000"

echo "Running End-to-End Routing Reliability Tests"
echo "--------------------------------------------"

echo "1. Source == Destination"
curl -s -X POST "$API_URL/v1/routes/discover" \
  -H "Content-Type: application/json" \
  -d '{"source_asset": {"code": "XLM"}, "destination_asset": {"code": "XLM"}, "amount": 100, "simulate": true, "risk_analysis": true, "validate_execution": true}' | grep '"failure_reason"'
echo ""

echo "2. Debug Diagnostics (Non-existent path)"
curl -s "$API_URL/v1/routes/debug?source_code=FAKE&dest_code=USDC&dest_issuer=GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN" | grep '"failure_reason"'
echo ""

echo "3. Assets Graph Check"
curl -s "$API_URL/v1/graph/assets?limit=1" | grep -E '"assets"|"detail"'
echo ""

echo "All tests completed."
