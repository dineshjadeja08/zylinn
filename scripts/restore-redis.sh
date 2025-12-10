#!/bin/bash
#
# Redis Restore Script
# Restores Redis from RDB backup file
#

set -euo pipefail

# Configuration
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.rdb.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /backups/redis/*.rdb.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=========================================="
echo "Redis Restore Script"
echo "=========================================="
echo "Server: ${REDIS_HOST}:${REDIS_PORT}"
echo "Backup file: $BACKUP_FILE"
echo ""

# Confirmation prompt
read -p "⚠️  This will FLUSH all Redis data and restore from backup. Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "🔄 Starting restore..."

# Build redis-cli command
REDIS_CMD="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_CMD="$REDIS_CMD -a $REDIS_PASSWORD --no-auth-warning"
fi

# Get current key count
BEFORE_COUNT=$($REDIS_CMD DBSIZE | grep -oE '[0-9]+')
echo "Current keys: $BEFORE_COUNT"

# Flush all data
echo ""
echo "1️⃣  Flushing all Redis data..."
$REDIS_CMD FLUSHALL || {
    echo "❌ Failed to flush Redis"
    exit 1
}

# Find Redis data directory
RDB_PATHS=(
    "/data/dump.rdb"
    "/var/lib/redis/dump.rdb"
    "./dump.rdb"
)

RDB_TARGET=""
for path in "${RDB_PATHS[@]}"; do
    DIR=$(dirname "$path")
    if [ -d "$DIR" ] && [ -w "$DIR" ]; then
        RDB_TARGET="$path"
        break
    fi
done

if [ -z "$RDB_TARGET" ]; then
    echo "❌ Could not find writable Redis data directory"
    echo "   Searched in: ${RDB_PATHS[*]}"
    exit 1
fi

# Decompress and copy RDB file
echo "2️⃣  Copying backup to Redis data directory..."
if gunzip -c "$BACKUP_FILE" > "$RDB_TARGET"; then
    echo "✅ Backup file copied"
else
    echo "❌ Failed to copy backup file"
    exit 1
fi

# Restart Redis to load the RDB file
echo ""
echo "3️⃣  Restarting Redis to load backup..."
echo "⚠️  NOTE: You may need to restart Redis manually:"
echo "   docker-compose restart redis"
echo ""
read -p "Press Enter after Redis has been restarted..."

# Verify restore
echo ""
echo "🔍 Verifying restore..."
AFTER_COUNT=$($REDIS_CMD DBSIZE | grep -oE '[0-9]+')
echo "   Keys after restore: $AFTER_COUNT"

if [ "$AFTER_COUNT" -gt 0 ]; then
    echo "✅ Restore appears successful!"
else
    echo "⚠️  Warning: No keys found after restore"
fi

echo ""
echo "=========================================="
echo "Restore Summary"
echo "=========================================="
echo "Status: ✅ COMPLETE"
echo "Keys before: $BEFORE_COUNT"
echo "Keys after: $AFTER_COUNT"
echo "=========================================="
