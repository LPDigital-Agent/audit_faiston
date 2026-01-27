# test-quotes.ps1 - Test Carrier Quotes Agent
# Usage: .\scripts\test-quotes.ps1 -Username "your@email.com" -Password "yourpassword"

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,

    [Parameter(Mandatory=$true)]
    [string]$Password
)

# Cognito Configuration
$Region = "us-east-2"
$UserPoolId = "us-east-2_lkBXr4kjy"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"

# AgentCore Configuration - Carrier Orchestrator (deployed 2026-01-19)
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_carrier_orchestration-kn4vaP2h89"

Write-Host "=== Faiston Carrier Quotes Test ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Authenticating with Cognito..." -ForegroundColor Yellow

# Step 1: Get JWT Token from Cognito
try {
    $authBody = @{
        AuthFlow = "USER_PASSWORD_AUTH"
        ClientId = $ClientId
        AuthParameters = @{
            USERNAME = $Username
            PASSWORD = $Password
        }
    } | ConvertTo-Json -Depth 3

    $authResponse = Invoke-RestMethod `
        -Uri "https://cognito-idp.$Region.amazonaws.com/" `
        -Method POST `
        -Headers @{
            "Content-Type" = "application/x-amz-json-1.1"
            "X-Amz-Target" = "AWSCognitoIdentityProviderService.InitiateAuth"
        } `
        -Body $authBody

    $token = $authResponse.AuthenticationResult.AccessToken
    Write-Host "[OK] Authentication successful!" -ForegroundColor Green
}
catch {
    Write-Host "[FAIL] Authentication failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Call AgentCore
Write-Host ""
Write-Host "Calling get_shipping_quotes on AgentCore..." -ForegroundColor Yellow

$encodedArn = [System.Uri]::EscapeDataString($AgentArn)
$sessionId = "test-quotes-" + [guid]::NewGuid().ToString("N")

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = $sessionId
}

$body = @{
    action = "get_shipping_quotes"
    origin_cep = "04548-005"
    destination_cep = "01310-100"
    weight_kg = 2.5
    dimensions = @{
        length = 30
        width = 20
        height = 15
    }
    value = 500
    urgency = "normal"
} | ConvertTo-Json -Depth 3

$url = "https://bedrock-agentcore.$Region.amazonaws.com/runtimes/$encodedArn/invocations?qualifier=DEFAULT"

Write-Host "  Session: $sessionId" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body $body

    Write-Host "[OK] Response received!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== RESPONSE ===" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "[FAIL] Request failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}
