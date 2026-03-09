# HandsomeTranscribe Desktop Application Launcher
# Activates Python venv and launches the desktop GUI

# Get the script directory
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# Check if venv exists
$venvPath = Join-Path $scriptDir ".venv"
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

if (-Not (Test-Path $activateScript)) {
    Write-Host "ERROR: Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Please create it first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating Python virtual environment..." -ForegroundColor Cyan
& $activateScript

# Check if activation was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Launch the desktop application
Write-Host "Launching HandsomeTranscribe..." -ForegroundColor Green
python desktop_app.py

# Capture exit code
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "ERROR: Application exited with code $exitCode" -ForegroundColor Red
}

exit $exitCode
