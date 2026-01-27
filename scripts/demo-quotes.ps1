# demo-quotes.ps1 - Demo: Get Shipping Quotes from Carrier Agent
# Run: .\scripts\demo-quotes.ps1

$Region = "us-east-2"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_asset_management-uSuLPsFQNH"
$Username = "test@lpdigital.ai"
$Password = "TestUser123!"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DEMO: Carrier Quotes Agent" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Auth
Write-Host "[1/2] Authenticating..." -ForegroundColor Yellow
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
Write-Host "      OK - Token obtained" -ForegroundColor Green

# Step 2: Call Agent
Write-Host "[2/2] Calling get_shipping_quotes..." -ForegroundColor Yellow
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
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = "demo-" + [guid]::NewGuid().ToString("N")
} -Body $body

Write-Host "      OK - Response received" -ForegroundColor Green
Write-Host ""

# Parse and display
$text = $response.content[0].text

# Debug: show raw text if needed
# Write-Host "DEBUG: $text" -ForegroundColor Magenta

# Parse JSON - handle potential encoding issues
try {
    $data = $text | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Host "Parsing inner JSON..." -ForegroundColor Gray
    # Try parsing as string first
    $data = [System.Text.Json.JsonSerializer]::Deserialize($text, [System.Collections.Hashtable])
}

# Handle orchestrator envelope
if ($data.response) {
    $quotes = $data.response.quotes
    $recommendation = $data.response.recommendation
} else {
    $quotes = $data.quotes
    $recommendation = $data.recommendation
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SHIPPING QUOTES (Sao Paulo -> Sao Paulo)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($quotes -and $quotes.Count -gt 0) {
    foreach ($q in $quotes) {
        $status = if ($q.available) { "[OK]" } else { "[X]" }
        $color = if ($q.available) { "Green" } else { "Red" }
        Write-Host "  $status $($q.modal)" -ForegroundColor $color -NoNewline
        Write-Host " - R$ $($q.price) - $($q.delivery_days) dias" -ForegroundColor White
    }
    Write-Host ""
    if ($recommendation) {
        Write-Host "  RECOMMENDATION: $($recommendation.modal) - R$ $($recommendation.price)" -ForegroundColor Yellow
        Write-Host "  Reason: $($recommendation.reason)" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  SUCCESS - Agent is working!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "  No quotes returned. Raw response:" -ForegroundColor Red
    Write-Host $text -ForegroundColor Gray
}
