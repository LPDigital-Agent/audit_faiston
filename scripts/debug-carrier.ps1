# debug-carrier.ps1 - Debug Carrier Agent Response

$Region = "us-east-2"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_asset_management-uSuLPsFQNH"
$Username = "test@lpdigital.ai"
$Password = "TestUser123!"

# Auth
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

# Call Agent
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
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = "debug-" + [guid]::NewGuid().ToString("N")
} -Body $body

Write-Host "=== RAW RESPONSE ===" -ForegroundColor Cyan
$response | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "=== CONTENT[0].TEXT ===" -ForegroundColor Cyan
$text = $response.content[0].text
Write-Host $text
