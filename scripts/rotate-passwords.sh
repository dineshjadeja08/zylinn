#!/bin/bash
set -e

echo "🔄 Zylin AI Password Rotation Script"
echo "====================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (sudo ./rotate-passwords.sh)"
  exit 1
fi

# Service to rotate
SERVICE=$1

if [ -z "$SERVICE" ]; then
  echo "Usage: ./rotate-passwords.sh [postgres|redis|grafana|jwt|all]"
  echo
  echo "Services:"
  echo "  postgres - Rotate PostgreSQL database password"
  echo "  redis    - Rotate Redis cache password"
  echo "  grafana  - Rotate Grafana admin password"
  echo "  jwt      - Rotate JWT secret key (invalidates all tokens)"
  echo "  all      - Rotate all passwords (recommended quarterly)"
  exit 1
fi

rotate_postgres() {
  echo "🔄 Rotating PostgreSQL password..."
  NEW_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
  
  # Update database
  docker-compose exec -T postgres psql -U zylin_user -d zylin -c \
    "ALTER USER zylin_user WITH PASSWORD '$NEW_PASSWORD';" > /dev/null 2>&1
  
  # Update .env.production
  sed -i.bak "s/^DB_PASSWORD=.*/DB_PASSWORD=$NEW_PASSWORD/" .env.production
  
  # Restart dependent services
  docker-compose restart backend agent backup > /dev/null 2>&1
  
  echo "✅ PostgreSQL password rotated"
  echo "   New password: ${NEW_PASSWORD:0:8}...${NEW_PASSWORD: -4}"
  echo "   Services restarted: backend, agent, backup"
}

rotate_redis() {
  echo "🔄 Rotating Redis password..."
  NEW_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
  
  # Update .env.production
  sed -i.bak "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$NEW_PASSWORD/" .env.production
  
  # Restart Redis and dependent services
  docker-compose restart redis backend agent > /dev/null 2>&1
  
  # Wait for services to start
  sleep 5
  
  # Verify Redis connection
  if docker-compose exec -T redis redis-cli -a $NEW_PASSWORD PING > /dev/null 2>&1; then
    echo "✅ Redis password rotated"
    echo "   New password: ${NEW_PASSWORD:0:8}...${NEW_PASSWORD: -4}"
    echo "   Services restarted: redis, backend, agent"
  else
    echo "❌ Redis password rotation failed! Restoring backup..."
    mv .env.production.bak .env.production
    docker-compose restart redis backend agent > /dev/null 2>&1
    exit 1
  fi
}

rotate_grafana() {
  echo "🔄 Rotating Grafana admin password..."
  NEW_PASSWORD=$(openssl rand -base64 24)
  
  # Update .env.production
  sed -i.bak "s/^GRAFANA_PASSWORD=.*/GRAFANA_PASSWORD=$NEW_PASSWORD/" .env.production
  
  # Restart Grafana
  docker-compose restart grafana > /dev/null 2>&1
  
  echo "✅ Grafana password rotated"
  echo "   New password: $NEW_PASSWORD"
  echo "   Login at: http://localhost:3000 (username: admin)"
}

rotate_jwt() {
  echo "🔄 Rotating JWT secret key..."
  echo "⚠️  WARNING: This will invalidate all existing user sessions!"
  read -p "Continue? (yes/no): " CONFIRM
  
  if [ "$CONFIRM" != "yes" ]; then
    echo "❌ JWT rotation cancelled"
    return
  fi
  
  NEW_SECRET=$(openssl rand -hex 64)
  NEW_SALT=$(openssl rand -hex 32)
  
  # Update .env.production
  sed -i.bak "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$NEW_SECRET/" .env.production
  sed -i "s/^API_KEY_SALT=.*/API_KEY_SALT=$NEW_SALT/" .env.production
  
  # Restart backend
  docker-compose restart backend > /dev/null 2>&1
  
  echo "✅ JWT secret rotated"
  echo "   New JWT secret: ${NEW_SECRET:0:8}...${NEW_SECRET: -4}"
  echo "   New API salt: ${NEW_SALT:0:8}...${NEW_SALT: -4}"
  echo "   ⚠️  All users must re-authenticate!"
}

case $SERVICE in
  postgres)
    rotate_postgres
    ;;
  
  redis)
    rotate_redis
    ;;
  
  grafana)
    rotate_grafana
    ;;
  
  jwt)
    rotate_jwt
    ;;
  
  all)
    echo "🔄 Rotating ALL passwords..."
    echo "⚠️  This will restart all services and invalidate all sessions!"
    read -p "Continue? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
      echo "❌ Rotation cancelled"
      exit 1
    fi
    
    echo
    rotate_postgres
    echo
    rotate_redis
    echo
    rotate_grafana
    echo
    rotate_jwt
    
    echo
    echo "✅ All passwords rotated successfully!"
    echo "   Backup saved: .env.production.bak"
    ;;
  
  *)
    echo "❌ Invalid service: $SERVICE"
    echo "Valid options: postgres, redis, grafana, jwt, all"
    exit 1
    ;;
esac

echo
echo "====================================="
echo "✅ Rotation complete!"
echo
echo "Next steps:"
echo "1. Update password manager with new credentials"
echo "2. Test application: docker-compose ps"
echo "3. Delete backup: rm .env.production.bak (after verification)"
echo "4. Log rotation in security audit log"
echo
echo "Last rotation: $(date)" >> .password-rotation-log
