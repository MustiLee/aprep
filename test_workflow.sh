#!/bin/bash
set -e

echo "=========================================="
echo "END-TO-END WORKFLOW TEST"
echo "=========================================="
echo ""

# Step 1: List templates
echo "[1/4] Listing available templates..."
TEMPLATES=$(curl -s http://localhost:8000/api/v1/templates/list)
TEMPLATE_COUNT=$(echo $TEMPLATES | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
echo "✓ Found $TEMPLATE_COUNT templates"
echo ""

# Step 2: Generate variants
echo "[2/4] Generating 2 variants..."
VARIANTS=$(curl -s -X POST http://localhost:8000/api/v1/variants/generate \
  -H "Content-Type: application/json" \
  -d '{"template_id": "ap_calc_bc_t2_power_rule_polynomial_001", "count": 2}')
VARIANT_ID=$(echo $VARIANTS | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
echo "✓ Generated variants, first ID: $VARIANT_ID"
echo ""

# Step 3: Verify variant
echo "[3/4] Verifying variant: $VARIANT_ID..."
VERIFICATION=$(curl -s -X POST http://localhost:8000/api/v1/verification/verify \
  -H "Content-Type: application/json" \
  -d "{\"variant_id\": \"$VARIANT_ID\"}")
STATUS=$(echo $VERIFICATION | python3 -c "import sys, json; print(json.load(sys.stdin)['verification_status'])")
CONFIDENCE=$(echo $VERIFICATION | python3 -c "import sys, json; print(json.load(sys.stdin)['consensus']['confidence'])")
echo "✓ Verification complete: $STATUS (confidence: $CONFIDENCE)"
echo ""

# Step 4: Check health
echo "[4/4] Checking API health..."
HEALTH=$(curl -s http://localhost:8000/health)
HEALTH_STATUS=$(echo $HEALTH | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
echo "✓ API Health: $HEALTH_STATUS"
echo ""

echo "=========================================="
echo "✅ END-TO-END WORKFLOW COMPLETED"
echo "=========================================="
echo ""
echo "Summary:"
echo "  • Templates: $TEMPLATE_COUNT available"
echo "  • Variant Generated: $VARIANT_ID"
echo "  • Verification: $STATUS (confidence: $CONFIDENCE)"
echo "  • API Health: $HEALTH_STATUS"
