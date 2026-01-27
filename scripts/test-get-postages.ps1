# test-get-postages.ps1 - Test Get Postages via Carrier Orchestrator
# Usage: .\scripts\test-get-postages.ps1 -Username "your@email.com" -Password "yourpassword"
#
# Tests the GSI4-TenantQuery performance improvement (SCAN -> Query)
# Expected: Response in milliseconds instead of ~1.4 minutes

param(
    [Parameter(Mandatory=$false)]
    [string]$Username = "test@lpdigital.ai",

    [Parameter(Mandatory=$false)]
    [string]$Password = "TestUser123!",

    [Parameter(Mandatory=$false)]
    [string]$Status = ""  # Optional: filter by status (aguardando, em_transito, entregue, cancelado)
)

# Cognito Configuration
$Region = "us-east-2"
$UserPoolId = "us-east-2_lkBXr4kjy"
$ClientId = "7ovjm09dr94e52mpejvbu9v1cg"

# AgentCore - Carrier Orchestrator (deployed 2026-01-19)
$AgentArn = "arn:aws:bedrock-agentcore:us-east-2:377311924364:runtime/faiston_carrier_orchestration-kn4vaP2h89"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FAISTON - Get Postages Test" -ForegroundColor Cyan
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

# Step 2: Call AgentCore with get_postages action
Write-Host "[2/2] Calling get_postages on AgentCore..." -ForegroundColor Yellow

$encodedArn = [System.Uri]::EscapeDataString($AgentArn)
$sessionId = "test-postages-" + [guid]::NewGuid().ToString("N")

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" = $sessionId
}

# Build request body
$bodyObj = @{
    action = "get_postages"
}

# Add status filter if provided
if ($Status -ne "") {
    $bodyObj.status = $Status
    Write-Host "      Filter: status = $Status" -ForegroundColor Gray
} else {
    Write-Host "      Filter: none (all postings via GSI4)" -ForegroundColor Gray
}

$body = $bodyObj | ConvertTo-Json -Depth 3

$url = "https://bedrock-agentcore.$Region.amazonaws.com/runtimes/$encodedArn/invocations?qualifier=DEFAULT"

Write-Host "      Session: $sessionId" -ForegroundColor Gray

# Measure execution time
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body $body -TimeoutSec 120

    $stopwatch.Stop()
    $elapsed = $stopwatch.Elapsed

    Write-Host "      [OK] Response received!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  PERFORMANCE METRICS" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Response Time: $($elapsed.TotalSeconds.ToString("F2")) seconds" -ForegroundColor $(if ($elapsed.TotalSeconds -lt 10) { "Green" } else { "Yellow" })

    if ($elapsed.TotalSeconds -lt 10) {
        Write-Host "  [PASS] GSI4 Query is working! (was ~84 seconds with SCAN)" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Response slow - may still be using SCAN" -ForegroundColor Yellow
    }

    # Parse response - handle multiple response formats
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  POSTAGES RESPONSE" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    # Try to extract text from different response formats
    $text = $null

    # Format 1: AgentCore streaming format (content[0].text)
    if ($response.content -and $response.content[0] -and $response.content[0].text) {
        $text = $response.content[0].text
    }
    # Format 2: Direct response object
    elseif ($response.response) {
        $text = $response | ConvertTo-Json -Depth 10
    }
    # Format 3: Raw string response
    elseif ($response -is [string]) {
        $text = $response
    }
    # Format 4: Object with postings directly
    elseif ($response.postings) {
        $text = $response | ConvertTo-Json -Depth 10
    }
    else {
        Write-Host "  Raw response structure:" -ForegroundColor Gray
        $response | ConvertTo-Json -Depth 5
        return
    }

    try {
        # Parse if it's a string
        if ($text -is [string]) {
            $data = $text | ConvertFrom-Json
        } else {
            $data = $text
        }

        # Handle orchestrator envelope
        if ($data.response) {
            $result = $data.response
        } else {
            $result = $data
        }

        $postings = $result.postings
        $count = if ($result.count) { $result.count } else { $postings.Count }

        Write-Host "  Total Postings: $count" -ForegroundColor White
        Write-Host ""

        if ($postings -and $postings.Count -gt 0) {
            Write-Host "  Recent Postings:" -ForegroundColor White
            Write-Host "  ----------------" -ForegroundColor Gray

            foreach ($p in $postings | Select-Object -First 10) {
                $statusColor = switch ($p.status) {
                    "aguardando" { "Yellow" }
                    "em_transito" { "Cyan" }
                    "entregue" { "Green" }
                    "cancelado" { "Red" }
                    default { "White" }
                }

                $tracking = if ($p.tracking_code) { $p.tracking_code } else { "N/A" }
                $created = if ($p.created_at) { $p.created_at.Substring(0, 10) } else { "?" }

                Write-Host "    $($p.order_code)" -ForegroundColor White -NoNewline
                Write-Host " | " -NoNewline
                Write-Host "$($p.status.PadRight(12))" -ForegroundColor $statusColor -NoNewline
                Write-Host " | $tracking | $created" -ForegroundColor Gray
            }

            if ($postings.Count -gt 10) {
                Write-Host ""
                Write-Host "    ... and $($postings.Count - 10) more" -ForegroundColor Gray
            }
        } else {
            Write-Host "  No postings found" -ForegroundColor Gray
        }

    } catch {
        Write-Host "  Parse error: $_" -ForegroundColor Red
        Write-Host "  Raw text:" -ForegroundColor Gray
        Write-Host $text
    }
}
catch {
    $stopwatch.Stop()
    Write-Host "      [FAIL] Request failed after $($stopwatch.Elapsed.TotalSeconds.ToString("F2"))s" -ForegroundColor Red
    Write-Host "      Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "      Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TEST COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
