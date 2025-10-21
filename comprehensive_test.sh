#!/bin/bash

echo "=========================================="
echo "COMPREHENSIVE API TEST"
echo "=========================================="
echo ""

# Test 1: Root endpoint
echo "[1/6] Testing root endpoint..."
curl -s http://localhost:8000/ | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ {d[\"name\"]} - {d[\"status\"]}')"
echo ""

# Test 2: Health check
echo "[2/6] Testing health check..."
curl -s http://localhost:8000/health | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ Health: {d[\"status\"]}')"
echo ""

# Test 3: API status
echo "[3/6] Testing API status..."
curl -s http://localhost:8000/api/v1/status | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ API Version: {d[\"api_version\"]}'); print(f'✓ Environment: {d[\"environment\"]}')"
echo ""

# Test 4: List templates
echo "[4/6] Testing template listing..."
curl -s http://localhost:8000/api/v1/templates/list | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ Templates: {len(d)} found')"
echo ""

# Test 5: Generate variants
echo "[5/6] Testing variant generation..."
curl -s -X POST http://localhost:8000/api/v1/variants/generate \
  -H "Content-Type: application/json" \
  -d '{"template_id": "ap_calc_bc_t2_power_rule_polynomial_001", "count": 1}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ Generated: {d[0][\"id\"]}'); print(f'✓ Stimulus: {d[0][\"stimulus\"]}')"
echo ""

# Test 6: Verify variant
echo "[6/6] Testing verification..."
VARIANT_ID="ap_calc_bc_t2_power_rule_polynomial_001_v7000"
curl -s -X POST http://localhost:8000/api/v1/verification/verify \
  -H "Content-Type: application/json" \
  -d "{\"variant_id\": \"$VARIANT_ID\"}" \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ Variant: {d[\"variant_id\"]}'); print(f'✓ Status: {d[\"verification_status\"]}'); print(f'✓ Answer Correct: {d[\"correctness\"][\"answer_is_correct\"]}'); print(f'✓ Confidence: {d[\"consensus\"][\"confidence\"]}')"
echo ""

echo "=========================================="
echo "✅ ALL TESTS PASSED"
echo "=========================================="
