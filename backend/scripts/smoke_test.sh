#!/bin/bash
# API Smoke Test Script (Bash)
# This script tests the main API endpoints

BASE_URL="http://127.0.0.1:8000"
USERNAME="${SMOKE_TEST_USERNAME:-admin}"
PASSWORD="${SMOKE_TEST_PASSWORD:-admin123}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass_count=0
fail_count=0

check_result() {
    local test_name="$1"
    local status_code="$2"
    
    if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
        echo -e "${GREEN}[PASS]${NC} $test_name (HTTP $status_code)"
        ((pass_count++))
    else
        echo -e "${RED}[FAIL]${NC} $test_name (HTTP $status_code)"
        ((fail_count++))
    fi
}

echo "========================================"
echo "  API Smoke Test"
echo "========================================"
echo ""

# 1. Health Check
echo "1. Health Check"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
check_result "Health Check" "$STATUS"

# 2. Login
echo ""
echo "2. Admin Login"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)
check_result "Login" "$STATUS"
TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "  Token: ${TOKEN:0:20}..."

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Cannot continue without token. Exiting.${NC}"
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $TOKEN"

# 3. Get Current Admin
echo ""
echo "3. Get Current Admin"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/me" -H "$AUTH_HEADER")
check_result "Get Admin Info" "$STATUS"

# 4. Create Knowledge
echo ""
echo "4. Create Knowledge"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/knowledge" \
    -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d '{"name":"Python装饰器","summary":"闭包应用","difficulty":2,"keywords":["装饰器","闭包"]}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)
check_result "Create Knowledge" "$STATUS"
KNOWLEDGE_ID=$(echo "$BODY" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "  Knowledge ID: $KNOWLEDGE_ID"

# 5. Get Knowledge List
echo ""
echo "5. Get Knowledge List"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/knowledge?page=1&page_size=10" -H "$AUTH_HEADER")
check_result "Get Knowledge List" "$STATUS"

# 6. Create Second Knowledge
echo ""
echo "6. Create Second Knowledge"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/knowledge" \
    -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d '{"name":"Python闭包","summary":"函数式编程概念","difficulty":2}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)
check_result "Create Second Knowledge" "$STATUS"
KNOWLEDGE2_ID=$(echo "$BODY" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "  Knowledge 2 ID: $KNOWLEDGE2_ID"

# 7. Create Knowledge Relation
if [ -n "$KNOWLEDGE_ID" ] && [ -n "$KNOWLEDGE2_ID" ]; then
    echo ""
    echo "7. Create Knowledge Relation"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "$BASE_URL/api/v1/knowledge/$KNOWLEDGE_ID/relations" \
        -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        -d "{\"target_knowledge_id\":$KNOWLEDGE2_ID,\"relation_type\":\"prerequisite\"}")
    check_result "Create Knowledge Relation" "$STATUS"
fi

# 8. Create Single Choice Question
echo ""
echo "8. Create Single Choice Question"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/questions" \
    -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d '{
        "question_type":"SINGLE_CHOICE",
        "content":"Python中哪个关键字用于定义装饰器？",
        "answer":"A",
        "difficulty":2,
        "options":[
            {"option_key":"A","option_content":"@","is_correct":1,"sort_order":0},
            {"option_key":"B","option_content":"#","is_correct":0,"sort_order":1},
            {"option_key":"C","option_content":"$","is_correct":0,"sort_order":2},
            {"option_key":"D","option_content":"&","is_correct":0,"sort_order":3}
        ],
        "knowledge_ids":['$KNOWLEDGE_ID']
    }')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)
check_result "Create Single Choice Question" "$STATUS"
QUESTION_ID=$(echo "$BODY" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "  Question ID: $QUESTION_ID"

# 9. Create True/False Question
echo ""
echo "9. Create True/False Question"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/questions" \
    -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d '{"question_type":"TRUE_FALSE","content":"装饰器只能用于函数","answer":"FALSE","difficulty":1}')
check_result "Create True/False Question" "$STATUS"

# 10. Create Short Answer Question
echo ""
echo "10. Create Short Answer Question"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/questions" \
    -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d '{"question_type":"SHORT_ANSWER","content":"解释装饰器","answer":"高阶函数","difficulty":3}')
check_result "Create Short Answer Question" "$STATUS"

# 11. Get Question List
echo ""
echo "11. Get Question List"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/questions?page=1&page_size=10" -H "$AUTH_HEADER")
check_result "Get Question List" "$STATUS"

# 12. Upload TXT File
echo ""
echo "12. Upload TXT File"
echo "Test content" > /tmp/smoke_test.txt
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/import-tasks" \
    -H "$AUTH_HEADER" -F "file=@/tmp/smoke_test.txt")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)
check_result "Upload TXT File" "$STATUS"
TASK_ID=$(echo "$BODY" | grep -o '"task_id":[0-9]*' | cut -d':' -f2)
echo "  Task ID: $TASK_ID"

# 13. Get Import Task
if [ -n "$TASK_ID" ]; then
    echo ""
    echo "13. Get Import Task"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/import-tasks/$TASK_ID" -H "$AUTH_HEADER")
    check_result "Get Import Task" "$STATUS"
fi

# 14. Get Dashboard
echo ""
echo "14. Get Dashboard Overview"
RESPONSE=$(curl -s "$BASE_URL/api/v1/dashboard/overview" -H "$AUTH_HEADER")
echo "  Dashboard: $RESPONSE"

# Cleanup
rm -f /tmp/smoke_test.txt

echo ""
echo "========================================"
echo -e "  Results: ${GREEN}$pass_count passed${NC}, ${RED}$fail_count failed${NC}"
echo "========================================"
