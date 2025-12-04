#!/bin/bash
# Start Zylin Voice Agent
set -e

echo "🤖 Starting Zylin Voice Agent..."

# Change to agent directory
cd "$(dirname "$0")/.."

# Load environment variables
if [ -f "../.env" ]; then
    echo "📝 Loading environment variables from .env"
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Parse arguments
ROOM_NAME=""
CALL_ID=""
MOCK_MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --room)
            ROOM_NAME="$2"
            shift 2
            ;;
        --call-id)
            CALL_ID="$2"
            shift 2
            ;;
        --mock)
            MOCK_MODE="--mock"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check required arguments
if [ -z "$ROOM_NAME" ]; then
    echo "❌ Error: --room argument is required"
    echo "Usage: $0 --room <room-name> [--call-id <id>] [--mock]"
    exit 1
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

# Start the agent
if [ -n "$CALL_ID" ]; then
    echo "✅ Starting agent for room: $ROOM_NAME, call: $CALL_ID"
    python agent.py --room "$ROOM_NAME" --call-id "$CALL_ID" $MOCK_MODE
else
    echo "✅ Starting agent for room: $ROOM_NAME"
    python agent.py --room "$ROOM_NAME" $MOCK_MODE
fi
