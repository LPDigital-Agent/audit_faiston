# test-create-postage.ps1 - Test Create Postage via Carrier Orchestrator
# Usage: .\scripts\test-create-postage.ps1 -Username "your@email.com" -Password "yourpassword"

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

# AgentCore - Carrier Orchestrator (deployed 2026-01-19)
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_carrier_orchestration-kn4vaP2h89"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FAISTON - Create Postage Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get JWT Token from Cognito
Write-Host "[1/2] Authenticating with Cognito..." -ForegroundColor Yellow
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
    Write-Host "      [OK] Authentication successful!" -ForegroundColor Green
}
catch {
    Write-Host "      [FAIL] Authentication failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Call AgentCore with create_postage action
Write-Host "[2/2] Calling create_postage on AgentCore..." -ForegroundColor Yellow

$encodedArn = [System.Uri]::EscapeDataString($AgentArn)
$sessionId = "test-postage-" + [guid]::NewGuid().ToString("N")

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = $sessionId
}

# Postage request payload
$body = @{
    action = "create_postage"
    destination_cep = "01310100"
    destination_name = "Teste Faiston NEXO"
    destination_address = "Av Paulista, 1000"
    destination_city = "Sao Paulo"
    destination_state = "SP"
    weight_kg = 0.5
    dimensions = @{
        length = 30
        width = 20
        height = 10
    }
    declared_value = 100
    urgency = "normal"
    selected_quote = @{
        carrier = "Correios"
        carrier_type = "CORREIOS"
        modal = "PAC"
        price = 25.50
        delivery_days = 5
    }
} | ConvertTo-Json -Depth 4

$url = "https://bedrock-agentcore.$Region.amazonaws.com/runtimes/$encodedArn/invocations?qualifier=DEFAULT"

Write-Host "      Session: $sessionId" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body $body -TimeoutSec 120

    Write-Host "      [OK] Response received!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  CREATE POSTAGE RESPONSE" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "      [FAIL] Request failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "      Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TEST COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
