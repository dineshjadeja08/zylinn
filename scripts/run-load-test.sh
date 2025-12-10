#!/bin/bash
set -e

echo "🚀 Zylin AI Load Test Runner"
echo "============================="
echo

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
DURATION="${DURATION:-24m}"  # Total test duration
VUS="${VUS:-100}"            # Max virtual users

# Check if k6 is installed
if ! command -v k6 &> /dev/null; then
  echo "❌ k6 not found. Installing..."
  
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    brew install k6
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
    sudo apt-get update
    sudo apt-get install k6
  else
    echo "❌ Unsupported OS. Please install k6 manually: https://k6.io/docs/getting-started/installation/"
    exit 1
  fi
fi

echo "✅ k6 version: $(k6 version)"
echo

# Check backend health
echo "🔍 Checking backend health..."
if curl -sf "${BASE_URL}/health" > /dev/null; then
  echo "✅ Backend is healthy"
else
  echo "❌ Backend is not reachable at ${BASE_URL}"
  echo "   Start services: docker-compose up -d"
  exit 1
fi

echo
echo "📊 Test Configuration"
echo "====================="
echo "Base URL: ${BASE_URL}"
echo "Duration: ${DURATION}"
echo "Max VUs: ${VUS}"
echo

# Create test users if needed
echo "👥 Setting up test users..."
for i in {1..3}; do
  EMAIL="test${i}@example.com"
  PASSWORD="TestPass123!"
  
  curl -sf -X POST "${BASE_URL}/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"name\":\"Test User ${i}\"}" \
    > /dev/null 2>&1 || true
done

echo "✅ Test users ready"
echo

# Start Prometheus/Grafana if not running
echo "📈 Checking monitoring stack..."
if docker-compose ps prometheus | grep -q "Up"; then
  echo "✅ Prometheus is running (http://localhost:9090)"
else
  echo "⚠️  Prometheus is not running. Metrics won't be collected."
  echo "   Start with: docker-compose up -d prometheus grafana"
fi

echo
echo "🚀 Starting load test..."
echo "========================="
echo

# Run load test
k6 run \
  --out json=load-test-results.json \
  --summary-export=load-test-summary.json \
  -e BASE_URL="${BASE_URL}" \
  scripts/load-test.js

echo
echo "✅ Load test complete!"
echo

# Generate report
echo "📊 Generating report..."
echo

if [ -f load-test-summary.json ]; then
  echo "📄 Summary Report"
  echo "================="
  
  # Parse JSON with jq if available
  if command -v jq &> /dev/null; then
    echo "Total Requests: $(jq '.metrics.http_reqs.values.count' load-test-summary.json)"
    echo "Failed Requests: $(jq '.metrics.http_req_failed.values.fails' load-test-summary.json)"
    echo "Average Response Time: $(jq '.metrics.http_req_duration.values.avg' load-test-summary.json)ms"
    echo "95th Percentile: $(jq '.metrics.http_req_duration.values["p(95)"]' load-test-summary.json)ms"
    echo "99th Percentile: $(jq '.metrics.http_req_duration.values["p(99)"]' load-test-summary.json)ms"
  else
    cat load-test-summary.json
  fi
  
  echo
  echo "📂 Results saved to:"
  echo "   - load-test-results.json (detailed)"
  echo "   - load-test-summary.json (summary)"
fi

echo
echo "📈 View results in Grafana:"
echo "   http://localhost:3000"
echo
echo "🔍 Check logs for errors:"
echo "   docker-compose logs backend | grep ERROR"
echo "   docker-compose logs agent | grep ERROR"
echo
echo "✅ Done!"
