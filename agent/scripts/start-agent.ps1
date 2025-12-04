# Start Zylin Voice Agent (PowerShell)
# Usage: .\start-agent.ps1 -Room "test-room" [-CallId "call-123"] [-Mock]

param(
    [Parameter(Mandatory=$true)]
    [string]$Room,
    
    [Parameter(Mandatory=$false)]
    [string]$CallId,
    
    [Parameter(Mandatory=$false)]
    [switch]$Mock
)

Write-Host "🤖 Starting Zylin Voice Agent..." -ForegroundColor Green

# Change to agent directory
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

# Build command
$cmd = "python agent.py --room `"$Room`""

if ($CallId) {
    $cmd += " --call-id `"$CallId`""
    Write-Host "✅ Starting agent for room: $Room, call: $CallId" -ForegroundColor Green
} else {
    Write-Host "✅ Starting agent for room: $Room" -ForegroundColor Green
}

if ($Mock) {
    $cmd += " --mock"
    Write-Host "🎭 Running in MOCK mode" -ForegroundColor Yellow
}

# Start the agent
Invoke-Expression $cmd
