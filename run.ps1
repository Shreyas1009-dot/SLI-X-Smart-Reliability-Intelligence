Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SLI-X - Smart Reliability Intelligence Launcher" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[1/2] Running automated diagnostic test suite..." -ForegroundColor Cyan
pytest -v tests/test_diagnostics.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed! Please review errors above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/2] Starting SLI-X FastAPI Server on http://127.0.0.1:8001 ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow
Write-Host ""
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
