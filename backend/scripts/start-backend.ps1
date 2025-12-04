# Start Zylin Backend API (PowerShell)
# Usage: .\start-backend.ps1

Write-Host "🚀 Starting Zylin Backend API..." -ForegroundColor Green

# Change to backend directory
Set-Location $PSScriptRoot\..

# Load environment variables
if (Test-Path "..\.env") {
    Write-Host "📝 Loading environment variables from .env" -ForegroundColor Cyan
    Get-Content "..\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*?)\s*$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "🔨 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
pip install -q -r requirements.txt

# Create database tables
Write-Host "🗄️  Initializing database..." -ForegroundColor Cyan
python -c "from models import DatabaseManager; db = DatabaseManager(); db.create_tables(); print('Database initialized')"

# Start the backend
$port = $env:BACKEND_PORT
if (-not $port) { $port = "8000" }

Write-Host "✅ Starting FastAPI server on port $port..." -ForegroundColor Green
python app.py
