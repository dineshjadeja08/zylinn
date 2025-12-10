#!/bin/bash
#
# PostgreSQL Restore Script
# Restores database from backup file
#

set -euo pipefail

# Configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-zylin}"
DB_USER="${DB_USER:-zylin_user}"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /backups/postgres/*.sql.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=========================================="
echo "PostgreSQL Restore Script"
echo "=========================================="
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "Backup file: $BACKUP_FILE"
echo ""

# Confirmation prompt
read -p "⚠️  This will DROP and recreate the database. Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "🔄 Starting restore..."

# Drop existing database
echo "1️⃣  Dropping existing database..."
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d postgres \
    -c "DROP DATABASE IF EXISTS $DB_NAME;" || {
    echo "❌ Failed to drop database"
    exit 1
}

# Create new database
echo "2️⃣  Creating new database..."
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d postgres \
    -c "CREATE DATABASE $DB_NAME;" || {
    echo "❌ Failed to create database"
    exit 1
}

# Restore from backup
echo "3️⃣  Restoring from backup..."
if gunzip -c "$BACKUP_FILE" | PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --quiet; then
    
    echo "✅ Restore completed successfully!"
else
    echo "❌ Restore failed!"
    exit 1
fi

# Verify restore
echo ""
echo "🔍 Verifying restore..."
TABLE_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")

echo "   Tables restored: $TABLE_COUNT"

echo ""
echo "=========================================="
echo "Restore Summary"
echo "=========================================="
echo "Status: ✅ SUCCESS"
echo "Database: $DB_NAME"
echo "Tables: $TABLE_COUNT"
echo "=========================================="
