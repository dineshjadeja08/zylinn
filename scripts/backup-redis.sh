#!/bin/bash
#
# Redis Backup Script
# Performs Redis backup (RDB snapshot) and uploads to S3 (optional)
#

set -euo pipefail

# Configuration
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
BACKUP_DIR="${BACKUP_DIR:-/backups/redis}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-backups/redis}"

# Timestamp for backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"
BACKUP_FILENAME=$(basename "$BACKUP_FILE")

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "Redis Backup Script"
echo "=========================================="
echo "Server: ${REDIS_HOST}:${REDIS_PORT}"
echo "Backup file: $BACKUP_FILE"
echo "Timestamp: $TIMESTAMP"
echo ""

# Build redis-cli command
REDIS_CMD="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_CMD="$REDIS_CMD -a $REDIS_PASSWORD --no-auth-warning"
fi

# Trigger BGSAVE (background save)
echo "🔄 Triggering Redis BGSAVE..."
if $REDIS_CMD BGSAVE | grep -q "Background saving started"; then
    echo "✅ Background save initiated"
else
    echo "⚠️  BGSAVE may have already been in progress"
fi

# Wait for BGSAVE to complete
echo "⏳ Waiting for save to complete..."
RETRIES=0
MAX_RETRIES=60

while [ $RETRIES -lt $MAX_RETRIES ]; do
    SAVE_STATUS=$($REDIS_CMD LASTSAVE)
    sleep 1
    NEW_STATUS=$($REDIS_CMD LASTSAVE)
    
    if [ "$NEW_STATUS" != "$SAVE_STATUS" ]; then
        echo "✅ Save completed!"
        break
    fi
    
    RETRIES=$((RETRIES + 1))
    if [ $((RETRIES % 10)) -eq 0 ]; then
        echo "   Still waiting... ($RETRIES seconds)"
    fi
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo "⚠️  Timeout waiting for save, proceeding anyway..."
fi

# Copy RDB file from Redis container/data directory
echo ""
echo "📦 Copying RDB file..."

# Try to find dump.rdb in common locations
RDB_PATHS=(
    "/data/dump.rdb"
    "/var/lib/redis/dump.rdb"
    "./dump.rdb"
)

RDB_SOURCE=""
for path in "${RDB_PATHS[@]}"; do
    if [ -f "$path" ]; then
        RDB_SOURCE="$path"
        break
    fi
done

if [ -z "$RDB_SOURCE" ]; then
    echo "❌ Could not find dump.rdb file"
    echo "   Searched in: ${RDB_PATHS[*]}"
    exit 1
fi

# Copy and compress
if cp "$RDB_SOURCE" "$BACKUP_FILE"; then
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    BACKUP_FILENAME="${BACKUP_FILENAME}.gz"
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup completed successfully!"
    echo "   File: $BACKUP_FILE"
    echo "   Size: $BACKUP_SIZE"
else
    echo "❌ Failed to copy RDB file"
    exit 1
fi

# Upload to S3 (if configured)
if [ -n "$S3_BUCKET" ]; then
    echo ""
    echo "☁️  Uploading to S3..."
    
    if command -v aws &> /dev/null; then
        S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/${BACKUP_FILENAME}"
        
        if aws s3 cp "$BACKUP_FILE" "$S3_PATH" \
            --storage-class STANDARD_IA \
            --metadata "server=$REDIS_HOST,timestamp=$TIMESTAMP"; then
            
            echo "✅ Upload to S3 successful!"
            echo "   Location: $S3_PATH"
            
            # Remove local file after successful upload (optional)
            if [ "${KEEP_LOCAL_BACKUP:-true}" = "false" ]; then
                rm "$BACKUP_FILE"
                echo "   Local backup removed (uploaded to S3)"
            fi
        else
            echo "⚠️  S3 upload failed, keeping local backup"
        fi
    else
        echo "⚠️  AWS CLI not installed, skipping S3 upload"
    fi
fi

# Clean up old backups (local)
echo ""
echo "🧹 Cleaning up old backups..."
DELETED_COUNT=0

find "$BACKUP_DIR" -name "redis_*.rdb.gz" -type f -mtime +"$RETENTION_DAYS" | while read -r old_backup; do
    echo "   Deleting: $(basename "$old_backup")"
    rm "$old_backup"
    DELETED_COUNT=$((DELETED_COUNT + 1))
done

if [ $DELETED_COUNT -gt 0 ]; then
    echo "✅ Deleted $DELETED_COUNT old backup(s) (older than $RETENTION_DAYS days)"
else
    echo "   No old backups to delete"
fi

# Summary
echo ""
echo "=========================================="
echo "Backup Summary"
echo "=========================================="
echo "Status: ✅ SUCCESS"
echo "Backup: $BACKUP_FILENAME"
echo "Size: $BACKUP_SIZE"
[ -n "$S3_BUCKET" ] && echo "S3: $S3_BUCKET/$S3_PREFIX"
echo "Retention: $RETENTION_DAYS days"
echo "=========================================="
