# SSL/TLS Certificate Setup Guide

Complete guide for setting up HTTPS with Let's Encrypt SSL certificates for Zylin AI.

## Quick Start (Production)

```bash
# 1. Set your domain and email
export DOMAIN="yourdomain.com"
export EMAIL="admin@yourdomain.com"

# 2. Run the SSL setup script
chmod +x scripts/setup-ssl.sh
sudo ./scripts/setup-ssl.sh

# 3. Update nginx configuration with your domain
# Edit nginx/nginx.conf and replace yourdomain.com with your actual domain

# 4. Restart nginx
docker-compose restart nginx

# 5. Test HTTPS
curl -I https://yourdomain.com
```

## Prerequisites

### 1. Domain Setup

Your domain must be pointed to your server:

```bash
# Check DNS resolution
nslookup yourdomain.com
dig yourdomain.com A

# Should return your server's public IP address
```

**DNS Configuration Required:**
- `A` record: `yourdomain.com` → `YOUR_SERVER_IP`
- `A` record: `www.yourdomain.com` → `YOUR_SERVER_IP` (optional)

### 2. Firewall Configuration

Open ports 80 and 443:

```bash
# Ubuntu/Debian
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload

# CentOS/RHEL
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# Check ports
sudo netstat -tulpn | grep -E ':80|:443'
```

### 3. Stop Conflicting Services

Certbot needs port 80 temporarily:

```bash
# Stop nginx temporarily
docker-compose stop nginx

# Or if running other web servers
sudo systemctl stop apache2  # Ubuntu
sudo systemctl stop httpd    # CentOS
```

## SSL Setup Script

The `scripts/setup-ssl.sh` script automates the entire process:

### What It Does

1. **Installs Certbot** - Let's Encrypt client
2. **Obtains Certificate** - Uses standalone mode to get cert
3. **Copies Certificates** - Places them in `nginx/ssl/`
4. **Sets Up Auto-Renewal** - Configures cron job for renewals
5. **Validates Certificate** - Tests the certificate

### Usage

```bash
#!/bin/bash
# scripts/setup-ssl.sh

# Basic usage
sudo ./scripts/setup-ssl.sh

# With environment variables
export DOMAIN="yourdomain.com"
export EMAIL="admin@yourdomain.com"
sudo -E ./scripts/setup-ssl.sh

# Custom domain and email
sudo DOMAIN=api.example.com EMAIL=ssl@example.com ./scripts/setup-ssl.sh
```

### Script Features

```bash
# Certificate acquisition
certbot certonly \
  --standalone \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d "$DOMAIN" \
  -d "www.$DOMAIN"

# Auto-renewal cron job (runs daily at 3 AM)
0 3 * * * certbot renew --quiet --deploy-hook 'docker-compose restart nginx'

# Certificate validation
openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -text
```

## Manual Certificate Setup

If you prefer manual setup or need customization:

### Step 1: Install Certbot

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install certbot -y

# CentOS/RHEL
sudo yum install certbot -y

# macOS
brew install certbot

# Verify installation
certbot --version
```

### Step 2: Obtain Certificate

**Standalone Mode** (recommended for Docker):

```bash
# Stop nginx first
docker-compose stop nginx

# Get certificate
sudo certbot certonly \
  --standalone \
  --preferred-challenges http \
  --agree-tos \
  --email admin@yourdomain.com \
  -d yourdomain.com \
  -d www.yourdomain.com

# Certificates saved to:
# /etc/letsencrypt/live/yourdomain.com/
```

**Webroot Mode** (if nginx is running):

```bash
# Create webroot directory
mkdir -p /var/www/html/.well-known/acme-challenge

# Get certificate
sudo certbot certonly \
  --webroot \
  -w /var/www/html \
  --agree-tos \
  --email admin@yourdomain.com \
  -d yourdomain.com \
  -d www.yourdomain.com
```

### Step 3: Copy Certificates

```bash
# Create ssl directory
mkdir -p nginx/ssl

# Copy certificate files
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Set permissions
sudo chmod 644 nginx/ssl/cert.pem
sudo chmod 600 nginx/ssl/key.pem
```

### Step 4: Configure Nginx

Update `nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificate paths
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # SSL protocols and ciphers
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # SSL session cache
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS (HTTP Strict Transport Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Other security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Your application configuration
    location / {
        proxy_pass http://backend;
        # ... other proxy settings
    }
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}
```

### Step 5: Update Docker Compose

Ensure SSL directory is mounted:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro  # SSL certificates
  depends_on:
    - backend
```

### Step 6: Restart and Test

```bash
# Restart nginx
docker-compose restart nginx

# Test HTTPS
curl -I https://yourdomain.com

# Check certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com
```

## Certificate Auto-Renewal

Let's Encrypt certificates expire every 90 days. Set up auto-renewal:

### Cron Job Method

```bash
# Edit crontab
sudo crontab -e

# Add renewal job (runs daily at 3 AM)
0 3 * * * certbot renew --quiet --deploy-hook 'cd /path/to/zylinn && docker-compose restart nginx' >> /var/log/certbot-renew.log 2>&1

# Test renewal (dry run)
sudo certbot renew --dry-run
```

### Systemd Timer Method

```bash
# Create timer file
sudo nano /etc/systemd/system/certbot-renew.timer

# Add content:
[Unit]
Description=Certbot Renewal Timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target

# Enable and start timer
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer

# Check timer status
sudo systemctl list-timers
```

### Manual Renewal

```bash
# Force renewal (if expiring within 30 days)
sudo certbot renew

# Force renewal regardless of expiry
sudo certbot renew --force-renewal

# Copy updated certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Restart nginx
docker-compose restart nginx
```

## Testing and Validation

### SSL Certificate Test

```bash
# Check certificate details
openssl x509 -in nginx/ssl/cert.pem -noout -text

# Check expiry date
openssl x509 -in nginx/ssl/cert.pem -noout -dates

# Verify certificate chain
openssl verify -CAfile nginx/ssl/cert.pem nginx/ssl/cert.pem
```

### HTTPS Endpoint Test

```bash
# Test HTTPS connection
curl -I https://yourdomain.com

# Test with verbose SSL info
curl -vI https://yourdomain.com 2>&1 | grep -E 'SSL|TLS'

# Test SSL/TLS protocols
nmap --script ssl-enum-ciphers -p 443 yourdomain.com
```

### Online SSL Testers

Test your SSL configuration:

1. **SSL Labs**: https://www.ssllabs.com/ssltest/
2. **SSL Shopper**: https://www.sslshopper.com/ssl-checker.html
3. **Why No Padlock**: https://www.whynopadlock.com/

**Target Grade: A or A+**

## Troubleshooting

### Certificate Not Found

```bash
# List all certificates
sudo certbot certificates

# Check certificate files
ls -la /etc/letsencrypt/live/yourdomain.com/

# Verify nginx can access files
sudo docker-compose exec nginx ls -la /etc/nginx/ssl/
```

### Port 80 Already in Use

```bash
# Find process using port 80
sudo lsof -i :80
sudo netstat -tulpn | grep :80

# Stop conflicting service
sudo systemctl stop apache2  # or nginx, httpd, etc.

# Run certbot again
sudo ./scripts/setup-ssl.sh
```

### Certificate Validation Failed

```bash
# Check DNS resolution
nslookup yourdomain.com
dig yourdomain.com A

# Test HTTP reachability
curl -I http://yourdomain.com/.well-known/acme-challenge/test

# Check firewall
sudo ufw status
sudo iptables -L -n
```

### Nginx Won't Start

```bash
# Test nginx configuration
sudo docker-compose exec nginx nginx -t

# Check nginx logs
docker-compose logs nginx

# Common issues:
# - Wrong certificate paths
# - Missing ssl_certificate or ssl_certificate_key
# - Syntax errors in nginx.conf
```

### Certificate Expired

```bash
# Check expiry
openssl x509 -in nginx/ssl/cert.pem -noout -dates

# Renew immediately
sudo certbot renew --force-renewal

# Copy new certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Restart nginx
docker-compose restart nginx
```

### Auto-Renewal Not Working

```bash
# Check cron logs
sudo grep CRON /var/log/syslog

# Check certbot logs
sudo cat /var/log/letsencrypt/letsencrypt.log

# Test renewal manually
sudo certbot renew --dry-run

# Check cron job exists
sudo crontab -l | grep certbot
```

## Security Best Practices

### 1. Strong SSL Configuration

Already configured in `nginx.conf`:

```nginx
# Use modern protocols only
ssl_protocols TLSv1.2 TLSv1.3;

# Strong cipher suites
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;

# HSTS (force HTTPS)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### 2. Certificate Monitoring

Monitor certificate expiry:

```bash
# Add to Prometheus (monitoring/prometheus.yml)
- job_name: 'ssl_expiry'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
      - https://yourdomain.com
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox-exporter:9115
```

### 3. Regular Audits

```bash
# Weekly SSL audit script
#!/bin/bash
echo "SSL Audit - $(date)"
openssl x509 -in nginx/ssl/cert.pem -noout -dates
openssl x509 -in nginx/ssl/cert.pem -noout -subject
curl -I https://yourdomain.com | head -n 1
```

### 4. Backup Certificates

```bash
# Backup Let's Encrypt directory
sudo tar -czf letsencrypt-backup-$(date +%Y%m%d).tar.gz /etc/letsencrypt/

# Upload to S3
aws s3 cp letsencrypt-backup-*.tar.gz s3://your-backup-bucket/ssl/
```

## Alternative: Self-Signed Certificate (Development)

For local development or testing:

```bash
# Generate self-signed certificate (1 year validity)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Zylin/CN=localhost"

# Restart nginx
docker-compose restart nginx

# Test (ignore certificate warning)
curl -k -I https://localhost
```

**Note**: Self-signed certificates will show browser warnings. Only use for development!

## Cost Analysis

### Let's Encrypt (FREE)

- **Certificate Cost**: $0
- **Renewal**: Automatic, free forever
- **Validation**: Domain validation (DV)
- **Wildcard Support**: Yes (with DNS challenge)

### Comparison

| Feature | Let's Encrypt | Paid SSL |
|---------|---------------|----------|
| Cost | FREE | $50-$300/year |
| Validation | DV | DV, OV, EV |
| Renewal | Auto (90 days) | Manual (1-2 years) |
| Support | Community | Premium |
| Trust | Excellent | Excellent |

**Recommendation**: Use Let's Encrypt for production. It's free, trusted, and automated.

## Production Checklist

- [ ] Domain DNS configured correctly
- [ ] Firewall allows ports 80 and 443
- [ ] Certbot installed and tested
- [ ] SSL certificates obtained and copied
- [ ] Nginx configured with correct domain
- [ ] HTTP to HTTPS redirect enabled
- [ ] HSTS header enabled
- [ ] Auto-renewal cron job set up
- [ ] Certificate expiry monitoring enabled
- [ ] SSL configuration tested (SSL Labs A+ grade)
- [ ] Backup certificates to S3
- [ ] Document certificate renewal process

## Support

**Certificate Issues:**
- Let's Encrypt Community: https://community.letsencrypt.org/
- Certbot Documentation: https://certbot.eff.org/docs/

**Nginx SSL:**
- Mozilla SSL Generator: https://ssl-config.mozilla.org/
- Nginx SSL Documentation: https://nginx.org/en/docs/http/configuring_https_servers.html

---

✅ **Status**: SSL setup complete with Let's Encrypt and auto-renewal
🔒 **Security**: TLS 1.2/1.3, HSTS enabled, A+ grade configuration
🔄 **Maintenance**: Certificates auto-renew every 90 days
💰 **Cost**: FREE with Let's Encrypt
