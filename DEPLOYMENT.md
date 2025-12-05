# Zylin AI Voice Agent - Production Deployment Guide

This guide walks you through deploying the Zylin AI Voice Agent as a production-ready SaaS platform.

## 🏗️ Architecture Overview

The production deployment uses Docker Compose to orchestrate 7 services:

1. **PostgreSQL** - Primary database for multi-tenant data
2. **Redis** - Caching and session management
3. **Backend** (2 replicas) - FastAPI REST API with authentication
4. **Agent** - LiveKit voice agent with LLM integration
5. **Nginx** - Reverse proxy with rate limiting and SSL
6. **Prometheus** - Metrics collection
7. **Grafana** - Monitoring dashboards

## 📋 Prerequisites

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Domain name** with DNS configured (for SSL certificates)
- **API Keys**:
  - OpenAI API key (for GPT-4o-mini)
  - AssemblyAI API key (for STT)
  - ElevenLabs API key (for TTS)
  - LiveKit Cloud credentials (or self-hosted LiveKit server)
- **SSL certificates** (Let's Encrypt recommended)

## 🔧 Setup Steps

### 1. Clone and Prepare Environment

```bash
cd c:\Users\VIKNESH B\OneDrive\Desktop\zylinn
```

### 2. Configure Environment Variables

Create a production environment file:

```bash
cp .env.production .env
```

Edit `.env` and fill in all required values:

```bash
# Database - Use strong passwords in production
DATABASE_URL=postgresql://zylinn_user:YOUR_STRONG_PASSWORD@postgres:5432/zylinn_db

# Redis
REDIS_URL=redis://redis:6379/0

# LiveKit
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_secret

# OpenAI
OPENAI_API_KEY=sk-YOUR_OPENAI_API_KEY
LLM_MODEL=gpt-4o-mini

# AssemblyAI STT (Production)
STT_PROVIDER=assemblyai
ASSEMBLYAI_API_KEY=your_assemblyai_api_key

# ElevenLabs TTS (Production)
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_voice_id

# Security
JWT_SECRET_KEY=YOUR_GENERATED_JWT_SECRET_32_CHARS_MIN
JWT_ALGORITHM=HS256
API_KEY_SALT=YOUR_RANDOM_SALT_16_CHARS_MIN

# CORS - Set to your frontend domains
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
AUTH_RATE_LIMIT_PER_MINUTE=5

# Feature Flags
ENABLE_USAGE_TRACKING=true
ENABLE_WEBHOOKS=true
```

**Generate secure secrets:**

```powershell
# JWT Secret (32+ characters)
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# API Key Salt (16+ characters)
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_})
```

### 3. Configure SSL Certificates

Place your SSL certificates in the `nginx/` directory:

```
nginx/
  ├── nginx.conf
  ├── ssl/
  │   ├── cert.pem
  │   └── key.pem
```

**Using Let's Encrypt:**

```bash
# Install certbot
# For Windows, download from: https://certbot.eff.org/

# Generate certificates
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy to nginx directory
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem
```

Update `nginx/nginx.conf` with your domain name (replace `yourdomain.com`).

### 4. Initialize Database

The PostgreSQL database will auto-initialize on first startup using `scripts/init-db.sql`. This creates:

- Multi-tenant schema (customers, usage_logs, webhook_configs, api_key_audit)
- Call records, transcripts, appointments tables
- Indexes for performance
- Default admin customer

### 5. Build and Start Services

```bash
# Build all Docker images
docker-compose build

# Start all services
docker-compose up -d

# Check service health
docker-compose ps
```

Expected output (all services "healthy"):
```
NAME                STATUS              PORTS
zylinn-agent-1      Up (healthy)        
zylinn-backend-1    Up (healthy)        
zylinn-backend-2    Up (healthy)        
zylinn-postgres-1   Up (healthy)        5432/tcp
zylinn-redis-1      Up (healthy)        6379/tcp
zylinn-nginx-1      Up                  0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
zylinn-prometheus-1 Up                  9090/tcp
zylinn-grafana-1    Up                  0.0.0.0:3000->3000/tcp
```

### 6. Create First Customer Account

Connect to the PostgreSQL database:

```bash
docker-compose exec postgres psql -U zylinn_user -d zylinn_db
```

Generate an API key for a customer:

```python
# Run this in a Python shell with the auth module
from backend.auth import hash_api_key
import secrets

# Generate a random API key
api_key = secrets.token_urlsafe(32)
print(f"API Key: {api_key}")

# Hash it for storage
api_key_hash = hash_api_key(api_key)
print(f"Hash: {api_key_hash}")
```

Insert the customer:

```sql
INSERT INTO customers (
    customer_name, 
    email, 
    api_key_hash, 
    plan_type, 
    max_calls_per_month, 
    max_minutes_per_call
) VALUES (
    'Your Company Name',
    'admin@yourcompany.com',
    'YOUR_API_KEY_HASH_HERE',
    'pro',
    10000,
    30
);
```

**Save the generated API key** - this is what customers use to authenticate.

### 7. Test the Deployment

Test health endpoints:

```bash
# Backend health
curl https://yourdomain.com/health

# Expected: {"status": "healthy", "database": "connected"}
```

Test authenticated endpoint:

```bash
# List calls (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/calls

# Expected: [] (empty array if no calls yet)
```

### 8. Configure Monitoring

Access Grafana:

```
URL: https://yourdomain.com:3000
Username: admin
Password: admin (change on first login)
```

**Add dashboards:**

1. Go to Dashboards → Import
2. Import dashboard ID **1860** (Node Exporter Full)
3. Import dashboard ID **3662** (Prometheus 2.0 Overview)
4. Create custom dashboard for:
   - API request rates
   - Agent call duration
   - Customer usage metrics
   - Database query performance

## 🔒 Security Checklist

- ✅ All API keys stored as environment variables (never committed)
- ✅ API keys hashed with PBKDF2 (100,000 iterations)
- ✅ JWT tokens for session management
- ✅ Rate limiting enabled (60 req/min API, 5 req/min auth)
- ✅ CORS restricted to specific domains
- ✅ SSL/TLS encryption (HTTPS only)
- ✅ Security headers (HSTS, X-Frame-Options, CSP)
- ✅ PostgreSQL password authentication
- ✅ Redis password protection (set in .env)
- ✅ Customer data isolation (multi-tenancy)
- ✅ API key audit logging

**Additional recommendations:**

- Use **AWS Secrets Manager** or **HashiCorp Vault** for secrets
- Enable **database encryption at rest**
- Set up **automated backups** (PostgreSQL + Redis)
- Configure **fail2ban** or similar for brute-force protection
- Enable **container scanning** (Docker Bench, Trivy)

## 📊 Monitoring & Alerts

### Prometheus Metrics

Available at `http://localhost:9090`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `db_connections_active` - Active database connections
- `redis_connected_clients` - Redis client count
- `agent_calls_active` - Active voice agent calls

### Set Up Alerts

Edit `monitoring/prometheus.yml` to add alerting rules:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/alerts.yml
```

Create `monitoring/alerts.yml`:

```yaml
groups:
  - name: api_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate detected"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL database is down"
```

## 📈 Scaling

### Horizontal Scaling

Scale backend replicas:

```bash
docker-compose up -d --scale backend=4
```

Scale agent instances:

```bash
docker-compose up -d --scale agent=3
```

Nginx automatically load balances across all replicas.

### Vertical Scaling

Edit `docker-compose.yml` to adjust resource limits:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Database Optimization

1. **Connection pooling** - Increase `max_connections` in PostgreSQL
2. **Query optimization** - Use `EXPLAIN ANALYZE` for slow queries
3. **Indexing** - Already configured in `init-db.sql`
4. **Partitioning** - Partition large tables by date (usage_logs, transcripts)

## 🔄 Updates & Maintenance

### Deploy Updates

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose build

# Rolling update (zero downtime)
docker-compose up -d --no-deps --build backend
docker-compose up -d --no-deps --build agent
```

### Database Migrations

Create migration scripts in `scripts/migrations/`:

```sql
-- scripts/migrations/001_add_customer_tier.sql
ALTER TABLE customers ADD COLUMN tier VARCHAR(20) DEFAULT 'standard';
CREATE INDEX idx_customers_tier ON customers(tier);
```

Apply migration:

```bash
docker-compose exec postgres psql -U zylinn_user -d zylinn_db -f /scripts/migrations/001_add_customer_tier.sql
```

### Backup & Restore

**Automated backups:**

```bash
# Add to crontab (daily at 2 AM)
0 2 * * * docker-compose exec -T postgres pg_dump -U zylinn_user zylinn_db | gzip > /backups/zylinn_$(date +\%Y\%m\%d).sql.gz
```

**Restore from backup:**

```bash
gunzip < /backups/zylinn_20250101.sql.gz | docker-compose exec -T postgres psql -U zylinn_user -d zylinn_db
```

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs backend
docker-compose logs agent

# Check service status
docker-compose ps

# Restart specific service
docker-compose restart backend
```

### Database Connection Issues

```bash
# Test database connection
docker-compose exec postgres psql -U zylinn_user -d zylinn_db -c "SELECT 1;"

# Check DATABASE_URL format
echo $DATABASE_URL
```

### Rate Limiting Issues

Edit `nginx/nginx.conf`:

```nginx
# Increase rate limits
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=120r/m;  # Increase to 120/min
```

### High Memory Usage

```bash
# Check memory usage
docker stats

# Adjust limits in docker-compose.yml
services:
  backend:
    mem_limit: 2g
    mem_reservation: 1g
```

## 📚 API Documentation

Once deployed, API documentation is available at:

```
https://yourdomain.com/docs        # Swagger UI
https://yourdomain.com/redoc       # ReDoc
```

### Authentication

All protected endpoints require an API key:

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/calls
```

### Endpoints

- `GET /health` - Health check (no auth)
- `GET /` - API info (no auth)
- `GET /calls` - List calls (requires auth)
- `GET /calls/{call_id}` - Call details (requires auth + ownership)
- `GET /calls/{call_id}/transcripts` - Transcripts (requires auth + ownership)
- `GET /calls/{call_id}/replies` - Agent replies (requires auth + ownership)
- `GET /appointments` - List appointments (requires auth + "appointments" feature)
- `GET /calls/{call_id}/appointments` - Call appointments (requires auth + "appointments" feature)

## 🎯 Production Readiness Checklist

### ✅ Completed

- [x] Multi-tenant database schema
- [x] API key authentication with hashing
- [x] JWT token support
- [x] Rate limiting (API + auth endpoints)
- [x] CORS configuration
- [x] Docker orchestration
- [x] PostgreSQL with connection pooling
- [x] Redis caching
- [x] Nginx reverse proxy with SSL
- [x] Prometheus metrics
- [x] Grafana dashboards
- [x] Health checks on all services
- [x] Usage tracking for billing
- [x] Customer plan enforcement
- [x] Feature gating by plan
- [x] Database indexes for performance
- [x] Ownership validation on endpoints

### ⚠️ TODO Before Production

- [ ] Migrate secrets to vault (AWS Secrets Manager / HashiCorp Vault)
- [ ] Fix agent timeout issue (12-second shutdown)
- [ ] Implement real TTS (ElevenLabs integration)
- [ ] Set up automated backups (PostgreSQL + Redis)
- [ ] Configure log aggregation (ELK Stack / Datadog)
- [ ] Add alerting (PagerDuty / Opsgenie)
- [ ] Load testing (JMeter / k6)
- [ ] Penetration testing
- [ ] GDPR compliance review
- [ ] Customer onboarding flow
- [ ] Billing integration (Stripe)
- [ ] Email notifications (SendGrid)
- [ ] CI/CD pipeline (GitHub Actions)

## 📞 Support

For issues or questions:

- **GitHub Issues**: [Your Repo URL]
- **Email**: support@yourcompany.com
- **Docs**: https://docs.yourcompany.com

## 📄 License

[Your License Here]
