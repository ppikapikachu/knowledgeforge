# API Smoke Test Script (PowerShell)
# This script tests the main API endpoints

$BaseUrl = "http://127.0.0.1:8000"
$Username = if ($env:SMOKE_TEST_USERNAME) { $env:SMOKE_TEST_USERNAME } else { "admin" }
$Password = if ($env:SMOKE_TEST_PASSWORD) { $env:SMOKE_TEST_PASSWORD } else { "admin123" }

function Write-TestResult {
    param(
        [string]$TestName,
        [int]$StatusCode,
        [string]$Response
    )
    
    if ($StatusCode -ge 200 -and $StatusCode -lt 300) {
        Write-Host "[PASS] $TestName (HTTP $StatusCode)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $TestName (HTTP $StatusCode)" -ForegroundColor Red
        Write-Host "  Response: $Response" -ForegroundColor Yellow
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API Smoke Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Health Check
Write-Host "1. Health Check" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/health" -Method GET -ErrorAction Stop
    Write-TestResult "Health Check" $response.StatusCode $response.Content
} catch {
    Write-TestResult "Health Check" 0 $_.Exception.Message
}

# 2. Login
Write-Host "`n2. Admin Login" -ForegroundColor Yellow
$loginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    $loginData = ($response.Content | ConvertFrom-Json).data
    $Token = $loginData.access_token
    Write-TestResult "Login" $response.StatusCode $response.Content
    Write-Host "  Token: $($Token.Substring(0, 20))..." -ForegroundColor Gray
} catch {
    Write-TestResult "Login" 0 $_.Exception.Message
    Write-Host "Cannot continue without token. Exiting." -ForegroundColor Red
    exit 1
}

$Headers = @{ Authorization = "Bearer $Token"; "Content-Type" = "application/json" }

# 3. Get Current Admin
Write-Host "`n3. Get Current Admin" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/auth/me" -Method GET -Headers $Headers -ErrorAction Stop
    Write-TestResult "Get Admin Info" $response.StatusCode $response.Content
} catch {
    Write-TestResult "Get Admin Info" 0 $_.Exception.Message
}

# 4. Create Knowledge
Write-Host "`n4. Create Knowledge" -ForegroundColor Yellow
$knowledgeBody = @{
    name = "Python装饰器"
    summary = "Python装饰器是闭包的一种应用"
    content = "装饰器是一个接受函数作为参数的高阶函数..."
    difficulty = 2
    status = 1
    source_type = "MANUAL"
    keywords = @("装饰器", "闭包", "高阶函数")
} | ConvertTo-Json -Depth 3
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/knowledge" -Method POST -Body $knowledgeBody -Headers $Headers -ErrorAction Stop
    $knowledgeData = ($response.Content | ConvertFrom-Json).data
    $KnowledgeId = $knowledgeData.id
    Write-TestResult "Create Knowledge" $response.StatusCode $response.Content
    Write-Host "  Knowledge ID: $KnowledgeId" -ForegroundColor Gray
} catch {
    Write-TestResult "Create Knowledge" 0 $_.Exception.Message
}

# 5. Get Knowledge List
Write-Host "`n5. Get Knowledge List" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/knowledge?page=1&page_size=10" -Method GET -Headers $Headers -ErrorAction Stop
    Write-TestResult "Get Knowledge List" $response.StatusCode $response.Content
} catch {
    Write-TestResult "Get Knowledge List" 0 $_.Exception.Message
}

# 6. Create Second Knowledge
Write-Host "`n6. Create Second Knowledge" -ForegroundColor Yellow
$knowledge2Body = @{
    name = "Python闭包"
    summary = "闭包是函数式编程的重要概念"
    difficulty = 2
} | ConvertTo-Json -Depth 3
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/knowledge" -Method POST -Body $knowledge2Body -Headers $Headers -ErrorAction Stop
    $knowledge2Data = ($response.Content | ConvertFrom-Json).data
    $Knowledge2Id = $knowledge2Data.id
    Write-TestResult "Create Second Knowledge" $response.StatusCode $response.Content
    Write-Host "  Knowledge 2 ID: $Knowledge2Id" -ForegroundColor Gray
} catch {
    Write-TestResult "Create Second Knowledge" 0 $_.Exception.Message
}

# 7. Create Knowledge Relation
if ($KnowledgeId -and $Knowledge2Id) {
    Write-Host "`n7. Create Knowledge Relation" -ForegroundColor Yellow
    $relationBody = @{
        target_knowledge_id = $Knowledge2Id
        relation_type = "prerequisite"
    } | ConvertTo-Json
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/knowledge/$KnowledgeId/relations" -Method POST -Body $relationBody -Headers $Headers -ErrorAction Stop
        Write-TestResult "Create Knowledge Relation" $response.StatusCode $response.Content
    } catch {
        Write-TestResult "Create Knowledge Relation" 0 $_.Exception.Message
    }
}

# 8. Create Single Choice Question
Write-Host "`n8. Create Single Choice Question" -ForegroundColor Yellow
$questionBody = @{
    question_type = "SINGLE_CHOICE"
    content = "Python中哪个关键字用于定义装饰器？"
    answer = "A"
    analysis = "使用@符号加装饰器名称来应用装饰器"
    difficulty = 2
    status = "DRAFT"
    options = @(
        @{ option_key = "A"; option_content = "@"; is_correct = 1; sort_order = 0 },
        @{ option_key = "B"; option_content = "#"; is_correct = 0; sort_order = 1 },
        @{ option_key = "C"; option_content = "$"; is_correct = 0; sort_order = 2 },
        @{ option_key = "D"; option_content = "&"; is_correct = 0; sort_order = 3 }
    )
    knowledge_ids = @($KnowledgeId)
} | ConvertTo-Json -Depth 4
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/questions" -Method POST -Body $questionBody -Headers $Headers -ErrorAction Stop
    $questionData = ($response.Content | ConvertFrom-Json).data
    $QuestionId = $questionData.id
    Write-TestResult "Create Single Choice Question" $response.StatusCode
    Write-Host "  Question ID: $QuestionId" -ForegroundColor Gray
} catch {
    Write-TestResult "Create Single Choice Question" 0 $_.Exception.Message
}

# 9. Create Multiple Choice Question
Write-Host "`n9. Create Multiple Choice Question" -ForegroundColor Yellow
$multiBody = @{
    question_type = "MULTIPLE_CHOICE"
    content = "以下哪些是Python的内置装饰器？（多选）"
    answer = "A,C"
    difficulty = 3
    options = @(
        @{ option_key = "A"; option_content = "@staticmethod"; is_correct = 1; sort_order = 0 },
        @{ option_key = "B"; option_content = "@inject"; is_correct = 0; sort_order = 1 },
        @{ option_key = "C"; option_content = "@classmethod"; is_correct = 1; sort_order = 2 },
        @{ option_key = "D"; option_content = "@override"; is_correct = 0; sort_order = 3 }
    )
} | ConvertTo-Json -Depth 4
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/questions" -Method POST -Body $multiBody -Headers $Headers -ErrorAction Stop
    Write-TestResult "Create Multiple Choice Question" $response.StatusCode
} catch {
    Write-TestResult "Create Multiple Choice Question" 0 $_.Exception.Message
}

# 10. Create True/False Question
Write-Host "`n10. Create True/False Question" -ForegroundColor Yellow
$tfBody = @{
    question_type = "TRUE_FALSE"
    content = "Python装饰器只能用于函数，不能用于类。"
    answer = "FALSE"
    difficulty = 1
} | ConvertTo-Json -Depth 3
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/questions" -Method POST -Body $tfBody -Headers $Headers -ErrorAction Stop
    Write-TestResult "Create True/False Question" $response.StatusCode
} catch {
    Write-TestResult "Create True/False Question" 0 $_.Exception.Message
}

# 11. Create Short Answer Question
Write-Host "`n11. Create Short Answer Question" -ForegroundColor Yellow
$saBody = @{
    question_type = "SHORT_ANSWER"
    content = "请解释Python装饰器的工作原理。"
    answer = "装饰器是一个接受函数作为参数并返回新函数的高阶函数，使用@语法糖应用。"
    difficulty = 3
} | ConvertTo-Json -Depth 3
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/questions" -Method POST -Body $saBody -Headers $Headers -ErrorAction Stop
    Write-TestResult "Create Short Answer Question" $response.StatusCode
} catch {
    Write-TestResult "Create Short Answer Question" 0 $_.Exception.Message
}

# 12. Get Question List
Write-Host "`n12. Get Question List" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/questions?page=1&page_size=10" -Method GET -Headers $Headers -ErrorAction Stop
    Write-TestResult "Get Question List" $response.StatusCode
} catch {
    Write-TestResult "Get Question List" 0 $_.Exception.Message
}

# 13. Upload TXT File
Write-Host "`n13. Upload TXT File" -ForegroundColor Yellow
$testFile = "$env:TEMP\smoke_test.txt"
"这是一个测试文件内容。" | Out-File -FilePath $testFile -Encoding utf8
try {
    $form = @{ file = Get-Item $testFile }
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/import-tasks" -Method POST -Form $form -Headers @{ Authorization = "Bearer $Token" } -ErrorAction Stop
    $importData = ($response.Content | ConvertFrom-Json).data
    $TaskId = $importData.task_id
    Write-TestResult "Upload TXT File" $response.StatusCode
    Write-Host "  Task ID: $TaskId" -ForegroundColor Gray
} catch {
    Write-TestResult "Upload TXT File" 0 $_.Exception.Message
}

# 14. Get Import Task
if ($TaskId) {
    Write-Host "`n14. Get Import Task" -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/import-tasks/$TaskId" -Method GET -Headers $Headers -ErrorAction Stop
        Write-TestResult "Get Import Task" $response.StatusCode
    } catch {
        Write-TestResult "Get Import Task" 0 $_.Exception.Message
    }
}

# 15. Get Dashboard
Write-Host "`n15. Get Dashboard Overview" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/dashboard/overview" -Method GET -Headers $Headers -ErrorAction Stop
    Write-TestResult "Get Dashboard" $response.StatusCode
    Write-Host "  Dashboard Data: $($response.Content)" -ForegroundColor Gray
} catch {
    Write-TestResult "Get Dashboard" 0 $_.Exception.Message
}

# Cleanup
Remove-Item -Path $testFile -ErrorAction SilentlyContinue

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Smoke Test Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
