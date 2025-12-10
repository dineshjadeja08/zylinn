#!/bin/bash
#
# SSL Certificate Setup Script
# Obtains Let's Encrypt certificates using certbot
#

set -e

DOMAIN="${1:-}"
EMAIL="${2:-}"
NGINX_SSL_DIR="${NGINX_SSL_DIR:-./nginx/ssl}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: $0 <domain> <email>"
    echo ""
    echo "Example:"
    echo "  $0 api.zylin.ai admin@zylin.ai"
    exit 1
fi

echo "=========================================="
echo "SSL Certificate Setup"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo "SSL Directory: $NGINX_SSL_DIR"
echo ""

# Create SSL directory if it doesn't exist
mkdir -p "$NGINX_SSL_DIR"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y certbot
    elif command -v yum &> /dev/null; then
        sudo yum install -y certbot
    elif command -v brew &> /dev/null; then
        brew install certbot
    else
        echo "❌ Could not install certbot. Please install manually."
        exit 1
    fi
fi

echo "✅ Certbot installed"
echo ""

# Stop nginx if running (to free port 80)
if docker-compose ps | grep -q nginx; then
    echo "⏸️  Stopping nginx temporarily..."
    docker-compose stop nginx
    RESTART_NGINX=true
else
    RESTART_NGINX=false
fi

# Obtain certificate
echo "🔐 Obtaining SSL certificate..."
sudo certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --preferred-challenges http

if [ $? -eq 0 ]; then
    echo "✅ Certificate obtained successfully!"
    
    # Copy certificates to nginx directory
    echo "📋 Copying certificates..."
    sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$NGINX_SSL_DIR/cert.pem"
    sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$NGINX_SSL_DIR/key.pem"
    sudo chmod 644 "$NGINX_SSL_DIR/cert.pem"
    sudo chmod 600 "$NGINX_SSL_DIR/key.pem"
    
    echo "✅ Certificates copied to $NGINX_SSL_DIR"
else
    echo "❌ Certificate acquisition failed"
    exit 1
fi

# Set up auto-renewal cron job
echo ""
echo "⚙️  Setting up auto-renewal..."

CRON_JOB="0 3 * * * certbot renew --quiet --deploy-hook 'cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $NGINX_SSL_DIR/cert.pem && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $NGINX_SSL_DIR/key.pem && docker-compose restart nginx'"

(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -

echo "✅ Auto-renewal configured (daily at 3 AM)"

# Restart nginx
if [ "$RESTART_NGINX" = true ]; then
    echo ""
    echo "🔄 Restarting nginx..."
    docker-compose start nginx
fi

# Test certificate
echo ""
echo "🧪 Testing certificate..."
openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -dates
openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -subject

echo ""
echo "=========================================="
echo "SSL Setup Complete!"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "Certificate: $NGINX_SSL_DIR/cert.pem"
echo "Private Key: $NGINX_SSL_DIR/key.pem"
echo "Expires: $(openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -enddate | cut -d= -f2)"
echo "Auto-renewal: ✅ Enabled"
echo "=========================================="
