#!/bin/bash
#
# PostgreSQL Backup Script
# Performs full database backup and uploads to S3 (optional)
#

set -euo pipefail

# Configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-zylin}"
DB_USER="${DB_USER:-zylin_user}"
BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-backups/postgres}"

# Timestamp for backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/postgres_${DB_NAME}_${TIMESTAMP}.sql.gz"
BACKUP_FILENAME=$(basename "$BACKUP_FILE")

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "PostgreSQL Backup Script"
echo "=========================================="
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "Backup file: $BACKUP_FILE"
echo "Timestamp: $TIMESTAMP"
echo ""

# Perform backup
echo "🔄 Starting backup..."
if PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-acl \
    --verbose \
    2>&1 | gzip > "$BACKUP_FILE"; then
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup completed successfully!"
    echo "   File: $BACKUP_FILE"
    echo "   Size: $BACKUP_SIZE"
else
    echo "❌ Backup failed!"
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
            --metadata "database=$DB_NAME,timestamp=$TIMESTAMP"; then
            
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

find "$BACKUP_DIR" -name "postgres_${DB_NAME}_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" | while read -r old_backup; do
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
