# migrate-postings-gsi4.ps1 - Add GSI4 keys to existing postings
# Usage: .\scripts\migrate-postings-gsi4.ps1 [-DryRun]

param(
    [switch]$DryRun
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  POSTINGS GSI4 MIGRATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "migrate-postings-gsi4.py"

if ($DryRun) {
    Write-Host "Running in DRY RUN mode (no changes will be made)" -ForegroundColor Yellow
    Write-Host ""
    python $scriptPath --dry-run
} else {
    Write-Host "Running in LIVE mode (will update DynamoDB records)" -ForegroundColor Red
    Write-Host ""
    python $scriptPath
}
