#!/bin/bash
# Start Zylin Backend API
set -e

echo "🚀 Starting Zylin Backend API..."

# Change to backend directory
cd "$(dirname "$0")/.."

# Load environment variables
if [ -f "../.env" ]; then
    echo "📝 Loading environment variables from .env"
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔨 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Create database tables
echo "🗄️  Initializing database..."
python -c "from models import DatabaseManager; db = DatabaseManager(); db.create_tables(); print('Database initialized')"

# Start the backend
echo "✅ Starting FastAPI server on port ${BACKEND_PORT:-8000}..."
python app.py
