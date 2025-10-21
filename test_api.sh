#!/bin/bash

# Aprep AI Agent System - API Test Script
# Bu script API'yi test eder ve örnek workflow çalıştırır

echo "=================================="
echo "Aprep AI Agent System - API Test"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

API_URL="http://localhost:8001"

echo "1. Health Check..."
HEALTH=$(curl -s ${API_URL}/health)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ API is running${NC}"
    echo "Response: $HEALTH"
else
    echo -e "${RED}✗ API is not running. Please start with: uvicorn src.api.main:app${NC}"
    exit 1
fi

echo ""
echo "2. API Status Check..."
curl -s ${API_URL}/api/v1/status | python3 -m json.tool

echo ""
echo "3. Creating a Template..."
TEMPLATE_RESPONSE=$(curl -s -X POST ${API_URL}/api/v1/templates/ \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test_001",
    "course_id": "ap_calculus_bc",
    "unit_id": "u2_differentiation",
    "topic_id": "t2_power_rule",
    "learning_objectives": ["Apply power rule to polynomial functions"],
    "difficulty_target": [0.4, 0.7],
    "calculator_policy": "No-Calc",
    "misconceptions": ["Forgot to multiply by exponent", "Subtracted 1 instead of multiplying"]
  }')

if echo "$TEMPLATE_RESPONSE" | grep -q "template_id"; then
    echo -e "${GREEN}✓ Template created successfully${NC}"
    TEMPLATE_ID=$(echo "$TEMPLATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['template_id'])" 2>/dev/null)
    echo "Template ID: $TEMPLATE_ID"
else
    echo -e "${RED}✗ Template creation failed${NC}"
    echo "$TEMPLATE_RESPONSE"
    exit 1
fi

echo ""
echo "4. Generating 5 Variants..."
VARIANTS_RESPONSE=$(curl -s -X POST ${API_URL}/api/v1/variants/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"template_id\": \"${TEMPLATE_ID}\",
    \"count\": 5,
    \"seed_start\": 0
  }")

if echo "$VARIANTS_RESPONSE" | grep -q "id"; then
    echo -e "${GREEN}✓ Variants generated successfully${NC}"
    VARIANT_COUNT=$(echo "$VARIANTS_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null)
    echo "Generated $VARIANT_COUNT variants"

    # Get first variant ID
    VARIANT_ID=$(echo "$VARIANTS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)
    echo "First variant ID: $VARIANT_ID"
else
    echo -e "${RED}✗ Variant generation failed${NC}"
    echo "$VARIANTS_RESPONSE"
    exit 1
fi

echo ""
echo "5. Verifying First Variant..."
VERIFICATION_RESPONSE=$(curl -s -X POST ${API_URL}/api/v1/verification/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"variant_id\": \"${VARIANT_ID}\"
  }")

if echo "$VERIFICATION_RESPONSE" | grep -q "verification_status"; then
    echo -e "${GREEN}✓ Verification completed${NC}"
    echo "$VERIFICATION_RESPONSE" | python3 -m json.tool
else
    echo -e "${RED}✗ Verification failed${NC}"
    echo "$VERIFICATION_RESPONSE"
fi

echo ""
echo "=================================="
echo "Test Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  - Open API docs: ${API_URL}/docs"
echo "  - List templates: curl ${API_URL}/api/v1/templates/"
echo "  - List variants: curl ${API_URL}/api/v1/variants/"
