# validate-carrier.ps1 - Validate Carrier Agent Real Mode
# Checks: is_simulated=false, adapter=PostalServiceAdapter

$Region = "us-east-2"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"
# Carrier Orchestrator (deployed 2026-01-19)
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_carrier_orchestration-kn4vaP2h89"
$Username = "test@lpdigital.ai"
$Password = "TestUser123!"

Write-Host ""
Write-Host "========================================"
Write-Host "  CARRIER AGENT VALIDATION"
Write-Host "========================================"
Write-Host ""

# Auth
Write-Host "[1/3] Authenticating..." -ForegroundColor Yellow
$authBody = @{
    AuthFlow = "USER_PASSWORD_AUTH"
    ClientId = $ClientId
    AuthParameters = @{ USERNAME = $Username; PASSWORD = $Password }
} | ConvertTo-Json -Depth 3

$auth = Invoke-RestMethod -Uri "https://cognito-idp.$Region.amazonaws.com/" -Method POST -Headers @{
    "Content-Type" = "application/x-amz-json-1.1"
    "X-Amz-Target" = "AWSCognitoIdentityProviderService.InitiateAuth"
} -Body $authBody

$token = $auth.AuthenticationResult.AccessToken
Write-Host "      [OK] Token obtained" -ForegroundColor Green

# Call Agent
Write-Host "[2/3] Calling get_shipping_quotes..." -ForegroundColor Yellow
$body = @{
    action = "get_shipping_quotes"
    origin_cep = "04548-005"
    destination_cep = "01310-100"
    weight_kg = 2.5
    dimensions = @{ length = 30; width = 20; height = 15 }
    value = 500
    urgency = "normal"
} | ConvertTo-Json -Depth 3

$url = "https://bedrock-agentcore.$Region.amazonaws.com/runtimes/$([System.Uri]::EscapeDataString($AgentArn))/invocations?qualifier=DEFAULT"
$response = Invoke-RestMethod -Uri $url -Method POST -Headers @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = "validate-" + [guid]::NewGuid().ToString("N")
} -Body $body

Write-Host "      [OK] Response received" -ForegroundColor Green

# Parse response
Write-Host "[3/3] Validating response..." -ForegroundColor Yellow
$text = $response.content[0].text
$data = $text | ConvertFrom-Json

# Handle orchestrator envelope
if ($data.response) {
    $result = $data.response
} else {
    $result = $data
}

Write-Host ""
Write-Host "========================================"
Write-Host "  VALIDATION RESULTS"
Write-Host "========================================"
Write-Host ""

# Check is_simulated
$isSimulated = $result.is_simulated
$adapter = $result.adapter
$note = $result.note

Write-Host "  is_simulated: " -NoNewline
if ($isSimulated -eq $false) {
    Write-Host "false" -ForegroundColor Green
    Write-Host "  [PASS] Using REAL Correios API!" -ForegroundColor Green
} else {
    Write-Host "true" -ForegroundColor Red
    Write-Host "  [FAIL] Still using MOCK data!" -ForegroundColor Red
}

Write-Host ""
Write-Host "  adapter:      " -NoNewline
if ($adapter -eq "PostalServiceAdapter") {
    Write-Host $adapter -ForegroundColor Green
    Write-Host "  [PASS] Real adapter active!" -ForegroundColor Green
} elseif ($adapter -eq "MockShippingAdapter") {
    Write-Host $adapter -ForegroundColor Red
    Write-Host "  [FAIL] Mock adapter still in use!" -ForegroundColor Red
} else {
    Write-Host $adapter -ForegroundColor Yellow
}

if ($note) {
    Write-Host ""
    Write-Host "  note:         $note" -ForegroundColor Gray
}

Write-Host ""
Write-Host "  Quotes count: $($result.quotes.Count)"
Write-Host ""

# Show quotes
foreach ($q in $result.quotes) {
    $status = if ($q.available) { "[OK]" } else { "[X]" }
    $color = if ($q.available) { "Green" } else { "Red" }
    Write-Host "  $status $($q.modal) - R$ $($q.price) - $($q.delivery_days) dias" -ForegroundColor $color
}

Write-Host ""
Write-Host "========================================"
if ($isSimulated -eq $false -and $adapter -eq "PostalServiceAdapter") {
    Write-Host "  VALIDATION PASSED!" -ForegroundColor Green
} else {
    Write-Host "  VALIDATION FAILED!" -ForegroundColor Red
}
Write-Host "========================================"
Write-Host ""
