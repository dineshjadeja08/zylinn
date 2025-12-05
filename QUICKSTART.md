# 🚀 Quick Start Guide - Zylin Production Deployment

This is a condensed version of DEPLOYMENT.md for rapid deployment.

## Prerequisites Checklist

- [ ] Docker & Docker Compose installed
- [ ] Domain name with DNS configured
- [ ] OpenAI API key
- [ ] AssemblyAI API key
- [ ] ElevenLabs API key
- [ ] LiveKit credentials

## 5-Minute Setup

### 1. Configure Environment (2 min)

```bash
# Copy production template
cp .env.production .env

# Generate secrets (PowerShell)
$jwt = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
$salt = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | % {[char]$_})

Write-Host "JWT_SECRET_KEY=$jwt"
Write-Host "API_KEY_SALT=$salt"
```

Edit `.env` and replace:
- `YOUR_POSTGRES_PASSWORD` → Strong password
- `YOUR_JWT_SECRET` → Generated JWT secret
- `YOUR_API_SALT` → Generated salt
- `YOUR_OPENAI_KEY` → OpenAI API key
- `YOUR_ASSEMBLYAI_KEY` → AssemblyAI API key
- `YOUR_ELEVENLABS_KEY` → ElevenLabs API key
- `YOUR_LIVEKIT_URL` → LiveKit WebSocket URL
- `YOUR_LIVEKIT_KEY` → LiveKit API key
- `YOUR_LIVEKIT_SECRET` → LiveKit secret
- `yourdomain.com` → Your actual domain

### 2. Setup SSL (1 min)

```bash
# Create SSL directory
mkdir nginx/ssl

# Copy your certificates
# Option A: Let's Encrypt
cp /path/to/fullchain.pem nginx/ssl/cert.pem
cp /path/to/privkey.pem nginx/ssl/key.pem

# Option B: Self-signed (dev only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem
```

Update `nginx/nginx.conf`:
- Line 48: Replace `yourdomain.com` with your domain

### 3. Deploy (1 min)

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d

# Check health (wait 30 seconds)
docker-compose ps
```

All services should show "Up (healthy)".

### 4. Create First Customer (1 min)

```bash
# Run the API key generator
python generate_api_key.py
```

Follow prompts:
- Customer Name: Your Company
- Email: admin@yourcompany.com
- Plan: 3 (pro)

**Save the generated API key!** You won't see it again.

### 5. Test API

```bash
# Test health (no auth)
curl https://yourdomain.com/health

# Test authenticated endpoint
curl -H "X-API-Key: YOUR_GENERATED_KEY" https://yourdomain.com/calls
```

Expected responses:
```json
{"status": "healthy", "database": "connected"}
[]
```

## 🎉 You're Live!

Your production SaaS is now running at:

- **API**: https://yourdomain.com
- **Docs**: https://yourdomain.com/docs
- **Grafana**: https://yourdomain.com:3000 (admin/admin)
- **Prometheus**: http://localhost:9090 (internal only)

## Next Steps

1. **Change Grafana password** (default: admin/admin)
2. **Set up monitoring alerts** (see DEPLOYMENT.md)
3. **Configure backups** (PostgreSQL + Redis)
4. **Test voice calls** via LiveKit
5. **Onboard first real customer**

## Common Issues

### Services won't start
```bash
# Check logs
docker-compose logs backend
docker-compose logs postgres

# Restart specific service
docker-compose restart backend
```

### Database connection error
```bash
# Verify DATABASE_URL format
echo $DATABASE_URL

# Should be: postgresql://user:password@postgres:5432/dbname
```

### API returns 401 Unauthorized
- Check API key is correct
- Verify customer is active: `docker-compose exec postgres psql -U zylinn_user -d zylinn_db -c "SELECT * FROM customers;"`

### Nginx returns 502 Bad Gateway
```bash
# Backend not ready yet, wait 30 seconds
docker-compose logs backend

# Check backend health
docker-compose exec backend curl http://localhost:8000/health
```

## Scaling

Add more replicas:
```bash
# Scale backend to 4 instances
docker-compose up -d --scale backend=4

# Scale agent to 3 instances
docker-compose up -d --scale agent=3
```

## Monitoring

Access Grafana:
```
URL: https://yourdomain.com:3000
Username: admin
Password: admin (change immediately)
```

Import dashboards:
- **1860** - Node Exporter Full
- **3662** - Prometheus 2.0 Overview

## Security Checklist

- [ ] Changed Grafana default password
- [ ] Generated unique JWT_SECRET_KEY
- [ ] Generated unique API_KEY_SALT
- [ ] Using strong PostgreSQL password
- [ ] CORS set to actual domains (not "*")
- [ ] SSL certificates installed
- [ ] API keys never committed to git
- [ ] Firewall configured (only 80, 443 open)

## Full Documentation

See `DEPLOYMENT.md` for complete deployment guide.
See `PRODUCTION_SUMMARY.md` for infrastructure details.

## Support

Questions? Check:
- `README.md` - Project overview
- `RUNBOOK.md` - Operations guide
- `DEPLOYMENT.md` - Full deployment guide
