# test-carrier-health.ps1 - Test Carrier Orchestrator Health Check

$Region = "us-east-2"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_carrier_orchestration-kn4vaP2h89"
$Username = "test@lpdigital.ai"
$Password = "TestUser123!"

Write-Host ""
Write-Host "========================================"
Write-Host "  CARRIER ORCHESTRATOR HEALTH CHECK"
Write-Host "========================================"
Write-Host ""

# Auth
Write-Host "[1/2] Authenticating..." -ForegroundColor Yellow
$authBody = @{
    AuthFlow = "USER_PASSWORD_AUTH"
    ClientId = $ClientId
    AuthParameters = @{ USERNAME = $Username; PASSWORD = $Password }
} | ConvertTo-Json -Depth 3

try {
    $auth = Invoke-RestMethod -Uri "https://cognito-idp.$Region.amazonaws.com/" -Method POST -Headers @{
        "Content-Type" = "application/x-amz-json-1.1"
        "X-Amz-Target" = "AWSCognitoIdentityProviderService.InitiateAuth"
    } -Body $authBody
    # Use IdToken for JWT authorizer (not AccessToken)
    $token = $auth.AuthenticationResult.IdToken
    Write-Host "      [OK] IdToken obtained" -ForegroundColor Green
} catch {
    Write-Host "      [FAIL] Auth failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Call Agent
Write-Host "[2/2] Calling health_check..." -ForegroundColor Yellow
$body = @{
    action = "health_check"
} | ConvertTo-Json

$url = "https://bedrock-agentcore.$Region.amazonaws.com/runtimes/$([System.Uri]::EscapeDataString($AgentArn))/invocations?qualifier=DEFAULT"

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -Headers @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = "health-" + [guid]::NewGuid().ToString("N")
    } -Body $body -TimeoutSec 120

    Write-Host "      [OK] Response received" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "      [FAIL] Request failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  HEALTH CHECK COMPLETE"
Write-Host "========================================"
