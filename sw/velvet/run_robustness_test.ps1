# Run Sprint 9 Robustness Test (Manual Verification)
# Uses Google Gemini API for fast agentic logic testing.

$env:VELVET_LLM_ADAPTER = "google"
$env:VELVET_LLM_MODEL = "gemini-3-flash-preview"
$env:VELVET_LLM_GOOGLE_API_KEY = "AIzaSyDatwSprfQCDlYh5AMqiRWZxqJqLIXKJWo"
$env:PYTHONPATH = "d:\Open Projects\seamless_computing\sw\velvet"

Write-Host "------------------------------------------------------------" -ForegroundColor Magenta
Write-Host "Starting Velvet Nadir [Robustness Test Mode]" -ForegroundColor Magenta
Write-Host "------------------------------------------------------------" -ForegroundColor Magenta
Write-Host "Adapter: Google Gemini ($env:VELVET_LLM_MODEL)" -ForegroundColor Gray
Write-Host "Role: Universal Node (Host)" -ForegroundColor Gray
Write-Host "Goal: Manual verification of Mesh, Gateway, and Skills." -ForegroundColor Gray
Write-Host ""

# Check for API Key
if (-not $env:VELVET_LLM_GOOGLE_API_KEY) {
    Write-Host "WARNING: VELVET_LLM_GOOGLE_API_KEY not set!" -ForegroundColor Yellow
    Write-Host "Please set it before running, or the test will fail." -ForegroundColor Yellow
    Write-Host 'Example: $env:VELVET_LLM_GOOGLE_API_KEY = "your_key"' -ForegroundColor Gray
    Write-Host ""
    Read-Host "Press any key to exit..."
    exit
}

# Run Main
python -m velvet.main --llm gemini-3-flash-preview --llm-adapter google live | Tee-Object -FilePath "testing.log"

Write-Host ""
Write-Host "Test session ended. Press any key to exit..." -ForegroundColor Gray
Read-Host
