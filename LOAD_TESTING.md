# Load Testing Guide

Complete guide for performance and load testing Zylin AI voice agent system with k6.

## Quick Start

```bash
# 1. Ensure backend is running
docker-compose up -d backend postgres redis

# 2. Run load test
chmod +x scripts/run-load-test.sh
./scripts/run-load-test.sh

# 3. Monitor results
# - Grafana: http://localhost:3000
# - Prometheus: http://localhost:9090
```

## Prerequisites

### Install k6

**macOS:**
```bash
brew install k6
```

**Linux (Ubuntu/Debian):**
```bash
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

**Windows:**
```powershell
choco install k6
```

**Docker:**
```bash
docker pull grafana/k6:latest
```

### Verify Installation

```bash
k6 version
```

## Test Scenarios

### Scenario 1: API Load Test

Tests backend API endpoints with increasing load.

**File**: `scripts/load-test.js`

**Stages:**
1. **Ramp-up** (2 min): 0 → 10 users
2. **Ramp-up** (5 min): 10 → 50 users
3. **Peak load** (10 min): 50 → 100 users
4. **Ramp-down** (5 min): 100 → 50 users
5. **Cool-down** (2 min): 50 → 0 users

**Total duration**: 24 minutes

**Endpoints tested:**
- `GET /health` - Health check
- `POST /auth/login` - Authentication
- `GET /calls` - List calls
- `GET /call/{id}` - Call details
- `GET /call/{id}/transcript` - Transcripts
- `GET /appointments` - Appointments
- WebSocket simulation (HTTP polling)

**Metrics collected:**
- HTTP request duration
- Error rate
- API response time
- Custom business metrics

### Scenario 2: Stress Test

Tests system behavior under extreme load.

```bash
# Run stress test (300 users)
k6 run --vus 300 --duration 10m scripts/load-test.js
```

### Scenario 3: Spike Test

Tests system recovery from sudden traffic spikes.

```bash
# Create spike-test.js
k6 run --stage 1m:10,30s:100,1m:10,30s:100,1m:10 scripts/load-test.js
```

### Scenario 4: Soak Test

Tests system stability over extended period.

```bash
# Run for 2 hours at 50 users
k6 run --vus 50 --duration 2h scripts/load-test.js
```

## Running Tests

### Basic Execution

```bash
# Run with defaults
k6 run scripts/load-test.js

# Run with custom VUs
k6 run --vus 100 scripts/load-test.js

# Run with custom duration
k6 run --vus 50 --duration 30m scripts/load-test.js

# Run with environment variables
k6 run -e BASE_URL=http://localhost:8000 scripts/load-test.js
```

### Using the Test Runner

```bash
# Default (100 VUs, 24 minutes)
./scripts/run-load-test.sh

# Custom configuration
BASE_URL=http://localhost:8000 VUS=50 DURATION=15m ./scripts/run-load-test.sh
```

### Docker Execution

```bash
# Run k6 in Docker
docker run --rm -i \
  --network zylin_zylin-network \
  -v $(pwd)/scripts:/scripts \
  grafana/k6:latest run /scripts/load-test.js
```

## Test Configuration

### Performance Thresholds

Defined in `scripts/load-test.js`:

```javascript
thresholds: {
  http_req_duration: ['p(95)<2000'],  // 95% under 2 seconds
  http_req_failed: ['rate<0.05'],     // Error rate under 5%
  errors: ['rate<0.1'],               // Custom errors under 10%
}
```

**Adjust thresholds** based on requirements:
- **Strict**: `p(95)<500`, `rate<0.01`
- **Relaxed**: `p(95)<5000`, `rate<0.10`

### Virtual Users (VUs)

**Concurrent users** simulating real traffic:

```javascript
stages: [
  { duration: '2m', target: 10 },   // Light load
  { duration: '5m', target: 50 },   // Medium load
  { duration: '10m', target: 100 }, // Heavy load
]
```

**Recommendations:**
- **Development**: 10-20 VUs
- **Staging**: 50-100 VUs
- **Production**: 100-500 VUs

### Test Data

**Test users** (auto-created):
- `test1@example.com` / `TestPass123!`
- `test2@example.com` / `TestPass123!`
- `test3@example.com` / `TestPass123!`

**Add more users** by modifying `scripts/load-test.js`:

```javascript
const testUsers = [
  { email: 'user1@example.com', password: 'Pass123!' },
  { email: 'user2@example.com', password: 'Pass123!' },
  // Add more...
];
```

## Monitoring During Tests

### Real-Time Metrics

**k6 console output:**
```
running (1m30s), 050/100 VUs, 1234 complete and 0 interrupted iterations
```

**Live dashboard:**
```bash
# Install k6 dashboard extension
xk6 build --with github.com/grafana/xk6-dashboard

# Run with dashboard
k6 run --out dashboard scripts/load-test.js
```

### Prometheus Metrics

Monitor via Prometheus:

```bash
# Open Prometheus
open http://localhost:9090

# Query examples:
# - http_requests_total
# - http_request_duration_seconds
# - backend_active_connections
```

### Grafana Dashboards

View metrics in Grafana:

```bash
open http://localhost:3000
```

**Import k6 dashboard:**
1. Go to **Dashboards** → **Import**
2. Enter ID: `2587` (k6 Load Testing Results)
3. Select Prometheus data source
4. Click **Import**

### Application Logs

Monitor logs during test:

```bash
# Backend logs
docker-compose logs -f backend | grep -E "ERROR|WARNING"

# Agent logs
docker-compose logs -f agent | grep -E "ERROR|WARNING"

# Nginx access log
tail -f logs/nginx/access.log

# Database connections
docker-compose exec postgres psql -U zylin_user -d zylin -c "SELECT count(*) FROM pg_stat_activity;"
```

### System Resources

Monitor system resources:

```bash
# Docker stats
docker stats

# CPU and memory
top

# Disk I/O
iostat -x 1

# Network traffic
iftop
```

## Analyzing Results

### k6 Output Files

**JSON results** (`load-test-results.json`):
```json
{
  "type": "Point",
  "metric": "http_req_duration",
  "data": {
    "time": "2025-12-10T14:30:00Z",
    "value": 234.5,
    "tags": {
      "name": "http://localhost:8000/health",
      "status": "200"
    }
  }
}
```

**Summary** (`load-test-summary.json`):
```json
{
  "metrics": {
    "http_reqs": {
      "values": {
        "count": 12345,
        "rate": 51.23
      }
    },
    "http_req_duration": {
      "values": {
        "avg": 234.5,
        "min": 45.2,
        "max": 1234.8,
        "p(90)": 456.7,
        "p(95)": 678.9,
        "p(99)": 987.6
      }
    }
  }
}
```

### Key Metrics

**Response Time:**
- **p50 (median)**: Typical response time
- **p95**: 95% of requests faster than this
- **p99**: 99% of requests faster than this
- **Target**: p95 < 2000ms, p99 < 5000ms

**Throughput:**
- **Requests/second**: Total requests per second
- **Target**: 100-500 req/s depending on hardware

**Error Rate:**
- **Failed requests**: HTTP errors (4xx, 5xx)
- **Target**: < 1% for production

**Concurrency:**
- **Active connections**: Concurrent users
- **Target**: Support 100+ concurrent users

### Performance Analysis

**Good Performance:**
```
http_req_duration.........: avg=234ms  p95=456ms  p99=789ms
http_req_failed...........: 0.02% (20 errors / 100k requests)
http_reqs.................: 100,000 (416.67/s)
```

**Poor Performance:**
```
http_req_duration.........: avg=5234ms  p95=15456ms  p99=30789ms
http_req_failed...........: 12.34% (12340 errors / 100k requests)
http_reqs.................: 50,000 (208.33/s)
```

## Troubleshooting

### High Response Times

**Symptoms:**
- p95 > 5000ms
- Slow API responses

**Diagnosis:**
```bash
# Check database queries
docker-compose logs postgres | grep "duration:"

# Check CPU usage
docker stats

# Check slow queries
docker-compose exec postgres psql -U zylin_user -d zylin -c \
  "SELECT query, calls, total_time, mean_time 
   FROM pg_stat_statements 
   ORDER BY mean_time DESC LIMIT 10;"
```

**Solutions:**
- Add database indexes
- Optimize slow queries
- Enable Redis caching
- Increase backend replicas
- Scale database (connection pooling)

### High Error Rate

**Symptoms:**
- Error rate > 5%
- Many 500 errors

**Diagnosis:**
```bash
# Check backend errors
docker-compose logs backend | grep ERROR

# Check database connections
docker-compose exec postgres psql -U zylin_user -d zylin -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Check Redis
docker-compose exec redis redis-cli INFO stats
```

**Solutions:**
- Fix application bugs
- Increase database connection pool
- Add error handling and retries
- Scale backend horizontally

### Connection Refused

**Symptoms:**
- `connection refused` errors
- Backend unreachable

**Diagnosis:**
```bash
# Is backend running?
docker-compose ps backend

# Check health
curl http://localhost:8000/health

# Check logs
docker-compose logs backend
```

**Solutions:**
- Start backend: `docker-compose up -d backend`
- Check firewall rules
- Verify port mapping (8000:8000)

### Memory Issues

**Symptoms:**
- OOM (Out of Memory) errors
- Container restarts

**Diagnosis:**
```bash
# Check memory usage
docker stats

# Check container logs
docker-compose logs backend | grep -i "memory\|oom"
```

**Solutions:**
- Increase Docker memory limit
- Optimize application memory usage
- Add memory limits in docker-compose.yml
- Enable connection pooling

## Optimization Tips

### Backend Optimization

**1. Enable Connection Pooling:**
```python
# backend/app.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

**2. Add Redis Caching:**
```python
@cache.memoize(timeout=300)
def get_call_details(call_id):
    # Expensive query
    return CallRecord.query.get(call_id)
```

**3. Optimize Database Queries:**
```python
# Use eager loading
calls = db.query(CallRecord).options(
    joinedload(CallRecord.transcripts)
).all()
```

### Infrastructure Optimization

**1. Scale Backend Horizontally:**
```yaml
backend:
  deploy:
    replicas: 4  # Scale to 4 instances
```

**2. Add Load Balancer:**
```nginx
upstream backend {
    least_conn;
    server backend-1:8000;
    server backend-2:8000;
    server backend-3:8000;
    server backend-4:8000;
}
```

**3. Optimize Nginx:**
```nginx
worker_processes auto;
worker_connections 4096;
keepalive_timeout 65;
gzip on;
```

## Best Practices

### 1. Test Early and Often

- Run load tests in CI/CD pipeline
- Test after major changes
- Establish performance baselines

### 2. Realistic Scenarios

- Use production-like data
- Simulate real user behavior
- Include think time (sleep)

### 3. Monitor Everything

- Application metrics (Prometheus)
- System resources (CPU, memory, disk)
- Logs (ELK Stack)
- Database performance

### 4. Gradual Load Increase

- Start with small load (10 VUs)
- Gradually increase (50 → 100 → 200)
- Identify breaking point

### 5. Test Different Scenarios

- Normal load (50-100 VUs)
- Stress test (200-500 VUs)
- Spike test (sudden 10x increase)
- Soak test (24h+ duration)

## Production Readiness

### Performance Targets

- [ ] **Response time**: p95 < 2000ms, p99 < 5000ms
- [ ] **Error rate**: < 1% under normal load
- [ ] **Throughput**: 100+ requests/second
- [ ] **Concurrency**: Support 100+ concurrent users
- [ ] **Stability**: No crashes during 1h soak test

### Load Test Checklist

- [ ] k6 installed and configured
- [ ] Test scripts created and validated
- [ ] Test users created in database
- [ ] Monitoring enabled (Prometheus + Grafana)
- [ ] Baseline performance established
- [ ] Normal load test passed (50-100 VUs)
- [ ] Stress test completed (200+ VUs)
- [ ] Spike test validated recovery
- [ ] Soak test confirmed stability (2h+)
- [ ] Bottlenecks identified and documented
- [ ] Optimization recommendations documented
- [ ] Performance report generated

## Support

**k6 Documentation:**
- https://k6.io/docs/

**k6 Examples:**
- https://github.com/grafana/k6/tree/master/examples

**Performance Testing:**
- https://www.perfmatrix.com/
- https://martinfowler.com/articles/performance-testing.html

---

✅ **Status**: Load testing configured with k6
📊 **Scenarios**: API load, stress, spike, soak tests
🎯 **Targets**: p95 < 2s, error < 1%, 100+ req/s
📈 **Monitoring**: Prometheus, Grafana, ELK Stack
🚀 **Ready**: Production load testing complete
