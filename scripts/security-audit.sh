#!/bin/bash

echo "🔍 Zylin AI Security Audit"
echo "========================="
echo

# Check .env.production permissions
echo "📁 Checking .env.production permissions..."
PERMS=$(stat -c %a .env.production 2>/dev/null || stat -f %A .env.production 2>/dev/null)
if [ "$PERMS" == "600" ]; then
  echo "✅ .env.production permissions: $PERMS (secure)"
else
  echo "⚠️  .env.production permissions: $PERMS (should be 600)"
  echo "   Run: chmod 600 .env.production"
fi

# Check for default passwords
echo
echo "🔑 Checking for default passwords..."
if grep -q "changeme123\|admin\|password123" .env.production 2>/dev/null; then
  echo "❌ Default passwords detected! Please run: python generate_passwords.py"
else
  echo "✅ No default passwords found"
fi

# Check password strength
echo
echo "💪 Checking password strength..."
if [ -f .env.production ]; then
  DB_PASS=$(grep "^DB_PASSWORD=" .env.production | cut -d= -f2)
  REDIS_PASS=$(grep "^REDIS_PASSWORD=" .env.production | cut -d= -f2)
  JWT_SECRET=$(grep "^JWT_SECRET_KEY=" .env.production | cut -d= -f2)
  
  if [ ${#DB_PASS} -ge 32 ]; then
    echo "✅ PostgreSQL password: ${#DB_PASS} chars (strong)"
  else
    echo "⚠️  PostgreSQL password: ${#DB_PASS} chars (should be 32+)"
  fi
  
  if [ ${#REDIS_PASS} -ge 32 ]; then
    echo "✅ Redis password: ${#REDIS_PASS} chars (strong)"
  else
    echo "⚠️  Redis password: ${#REDIS_PASS} chars (should be 32+)"
  fi
  
  if [ ${#JWT_SECRET} -ge 64 ]; then
    echo "✅ JWT secret: ${#JWT_SECRET} chars (strong)"
  else
    echo "⚠️  JWT secret: ${#JWT_SECRET} chars (should be 64+)"
  fi
else
  echo "⚠️  .env.production not found"
fi

# Check SSL certificates
echo
echo "🔒 Checking SSL certificates..."
if [ -f "nginx/ssl/cert.pem" ]; then
  EXPIRY=$(openssl x509 -in nginx/ssl/cert.pem -noout -enddate 2>/dev/null | cut -d= -f2)
  DAYS_LEFT=$(( ($(date -d "$EXPIRY" +%s) - $(date +%s)) / 86400 ))
  
  if [ $DAYS_LEFT -lt 30 ]; then
    echo "⚠️  SSL certificate expires soon: $EXPIRY ($DAYS_LEFT days left)"
  else
    echo "✅ SSL certificate valid until: $EXPIRY ($DAYS_LEFT days left)"
  fi
else
  echo "⚠️  SSL certificate not found. Run: ./scripts/setup-ssl.sh"
fi

# Check nginx configuration
echo
echo "🌐 Checking nginx configuration..."
if grep -q "return 301 https" nginx/nginx.conf; then
  echo "✅ HTTP to HTTPS redirect enabled"
else
  echo "⚠️  HTTP to HTTPS redirect not enabled"
fi

if grep -q "Strict-Transport-Security" nginx/nginx.conf; then
  echo "✅ HSTS header enabled"
else
  echo "⚠️  HSTS header not enabled"
fi

# Check running services
echo
echo "🚀 Checking running services..."
if command -v docker-compose &> /dev/null; then
  docker-compose ps 2>/dev/null | grep -E "Up|running" | awk '{print "✅", $1, "is running"}'
else
  echo "⚠️  docker-compose not found"
fi

# Check for exposed secrets in git
echo
echo "🔍 Checking for exposed secrets in git..."
if git rev-parse --git-dir > /dev/null 2>&1; then
  if git log --all --full-history -- ".env*" 2>/dev/null | grep -q "commit"; then
    echo "⚠️  .env files found in git history! Consider using git-filter-repo"
  else
    echo "✅ No .env files in git history"
  fi
  
  if git check-ignore .env.production > /dev/null 2>&1; then
    echo "✅ .env.production in .gitignore"
  else
    echo "⚠️  .env.production NOT in .gitignore"
  fi
else
  echo "ℹ️  Not a git repository"
fi

# Check firewall
echo
echo "🔥 Checking firewall status..."
if command -v ufw &> /dev/null; then
  if sudo ufw status | grep -q "Status: active"; then
    echo "✅ UFW firewall is active"
    sudo ufw status numbered | grep -E "80|443|22" | head -n 3
  else
    echo "⚠️  UFW firewall is inactive"
  fi
elif command -v firewall-cmd &> /dev/null; then
  if sudo firewall-cmd --state 2>/dev/null | grep -q "running"; then
    echo "✅ firewalld is running"
  else
    echo "⚠️  firewalld is not running"
  fi
else
  echo "ℹ️  No firewall detected (ufw/firewalld)"
fi

# Check Docker socket permissions
echo
echo "🐳 Checking Docker security..."
if [ -e /var/run/docker.sock ]; then
  DOCKER_PERMS=$(stat -c %a /var/run/docker.sock 2>/dev/null || stat -f %A /var/run/docker.sock 2>/dev/null)
  if [ "$DOCKER_PERMS" == "660" ]; then
    echo "✅ Docker socket permissions: $DOCKER_PERMS (secure)"
  else
    echo "⚠️  Docker socket permissions: $DOCKER_PERMS (should be 660)"
  fi
fi

# Check SSH configuration
echo
echo "🔐 Checking SSH security..."
if [ -f /etc/ssh/sshd_config ]; then
  if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config; then
    echo "✅ SSH password authentication disabled"
  else
    echo "⚠️  SSH password authentication enabled (consider disabling)"
  fi
  
  if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config; then
    echo "✅ SSH root login disabled"
  else
    echo "⚠️  SSH root login enabled (consider disabling)"
  fi
fi

# Summary
echo
echo "========================="
echo "📊 Security Score"
echo "========================="

SCORE=0
MAX_SCORE=15

# Count checks
[ "$PERMS" == "600" ] && ((SCORE++))
! grep -q "changeme123\|admin\|password123" .env.production 2>/dev/null && ((SCORE++))
[ ${#DB_PASS} -ge 32 ] && ((SCORE++))
[ ${#REDIS_PASS} -ge 32 ] && ((SCORE++))
[ ${#JWT_SECRET} -ge 64 ] && ((SCORE++))
[ -f "nginx/ssl/cert.pem" ] && ((SCORE++))
grep -q "return 301 https" nginx/nginx.conf && ((SCORE++))
grep -q "Strict-Transport-Security" nginx/nginx.conf && ((SCORE++))
docker-compose ps 2>/dev/null | grep -q "Up" && ((SCORE++))
! git log --all --full-history -- ".env*" 2>/dev/null | grep -q "commit" && ((SCORE++))
git check-ignore .env.production > /dev/null 2>&1 && ((SCORE++))
[ "$DOCKER_PERMS" == "660" ] && ((SCORE++))
grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null && ((SCORE++))
grep -q "^PermitRootLogin no" /etc/ssh/sshd_config 2>/dev/null && ((SCORE++))

PERCENTAGE=$((SCORE * 100 / MAX_SCORE))

echo "Score: $SCORE / $MAX_SCORE ($PERCENTAGE%)"

if [ $PERCENTAGE -ge 90 ]; then
  echo "🎉 Excellent security posture!"
elif [ $PERCENTAGE -ge 70 ]; then
  echo "✅ Good security, minor improvements needed"
elif [ $PERCENTAGE -ge 50 ]; then
  echo "⚠️  Fair security, several improvements needed"
else
  echo "❌ Poor security, immediate action required!"
fi

echo
echo "✅ Security audit complete"
echo
echo "Next steps:"
echo "1. Review warnings above and fix issues"
echo "2. Run: python generate_passwords.py (if default passwords found)"
echo "3. Run: ./scripts/setup-ssl.sh (if SSL not configured)"
echo "4. Run: chmod 600 .env.production (if permissions wrong)"
echo "5. Schedule monthly audits with cron"
