# Automated Backup System

## Overview

Zylin AI includes a **fully automated backup system** for PostgreSQL and Redis with:

- ✅ **Scheduled daily backups** (2 AM PostgreSQL, 3 AM Redis)
- ✅ **Automatic retention management** (30 days default)
- ✅ **Optional S3 uploads** for off-site storage
- ✅ **Simple restore procedures**
- ✅ **Compression** (gzip) to save space
- ✅ **Health monitoring** and logging

---

## Quick Start

### 1. Enable Backups

Backups are **enabled by default** when using `docker-compose.yml`.

```bash
# Start all services including backup service
docker-compose up -d

# Check backup service is running
docker-compose ps backup
```

### 2. Configure Retention (Optional)

Edit `.env.production`:

```bash
BACKUP_RETENTION_DAYS=30  # Keep backups for 30 days (default)
```

### 3. Configure S3 (Optional, Recommended for Production)

```bash
BACKUP_S3_BUCKET=my-zylin-backups
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
```

### 4. Verify Backups

```bash
# Check backup logs
docker-compose logs backup

# List backup files
docker-compose exec backup ls -lh /backups/postgres/
docker-compose exec backup ls -lh /backups/redis/
```

---

## Architecture

### Backup Schedule

| Database | Time | Frequency | Retention |
|----------|------|-----------|-----------|
| PostgreSQL | 2:00 AM | Daily | 30 days |
| Redis | 3:00 AM | Daily | 30 days |

### Storage Locations

**Local Storage (always):**
- PostgreSQL: `/backups/postgres/postgres_zylin_YYYYMMDD_HHMMSS.sql.gz`
- Redis: `/backups/redis/redis_YYYYMMDD_HHMMSS.rdb.gz`

**S3 Storage (optional):**
- PostgreSQL: `s3://bucket/backups/postgres/postgres_zylin_YYYYMMDD_HHMMSS.sql.gz`
- Redis: `s3://bucket/backups/redis/redis_YYYYMMDD_HHMMSS.rdb.gz`

### Redis Persistence

Redis is configured with **AOF (Append-Only File)** persistence:
- **Mode**: `appendonly yes`
- **Fsync**: `everysec` (balance between durability and performance)
- **Benefits**: Near real-time durability, fast recovery

---

## Manual Backup

### PostgreSQL

```bash
# Manual backup (runs immediately)
docker-compose exec backup /scripts/backup-postgres.sh

# Output example:
# ==========================================
# PostgreSQL Backup Script
# ==========================================
# Database: zylin@postgres:5432
# Backup file: /backups/postgres/postgres_zylin_20241210_143052.sql.gz
# 
# 🔄 Starting backup...
# ✅ Backup completed successfully!
#    File: /backups/postgres/postgres_zylin_20241210_143052.sql.gz
#    Size: 15M
# ☁️  Uploading to S3...
# ✅ Upload to S3 successful!
```

### Redis

```bash
# Manual backup (runs immediately)
docker-compose exec backup /scripts/backup-redis.sh

# Output example:
# ==========================================
# Redis Backup Script
# ==========================================
# Server: redis:6379
# Backup file: /backups/redis/redis_20241210_143152.rdb.gz
# 
# 🔄 Triggering Redis BGSAVE...
# ✅ Background save initiated
# ⏳ Waiting for save to complete...
# ✅ Save completed!
# 📦 Copying RDB file...
# ✅ Backup completed successfully!
#    File: /backups/redis/redis_20241210_143152.rdb.gz
#    Size: 2.3M
```

---

## Restore Procedures

### PostgreSQL Restore

```bash
# 1. List available backups
docker-compose exec backup ls -lh /backups/postgres/

# 2. Stop application services (to prevent writes during restore)
docker-compose stop backend agent

# 3. Restore from backup
docker-compose exec backup /scripts/restore-postgres.sh /backups/postgres/postgres_zylin_20241210_020000.sql.gz

# Follow prompts:
# ⚠️  This will DROP and recreate the database. Continue? (yes/no): yes
# 
# 🔄 Starting restore...
# 1️⃣  Dropping existing database...
# 2️⃣  Creating new database...
# 3️⃣  Restoring from backup...
# ✅ Restore completed successfully!
# 
# 🔍 Verifying restore...
#    Tables restored: 12
# 
# ==========================================
# Restore Summary
# ==========================================
# Status: ✅ SUCCESS
# Database: zylin
# Tables: 12
# ==========================================

# 4. Restart application services
docker-compose start backend agent
```

### Redis Restore

```bash
# 1. List available backups
docker-compose exec backup ls -lh /backups/redis/

# 2. Stop Redis (to prevent writes during restore)
docker-compose stop redis

# 3. Restore from backup
docker-compose exec backup /scripts/restore-redis.sh /backups/redis/redis_20241210_030000.rdb.gz

# Follow prompts:
# ⚠️  This will FLUSH all Redis data and restore from backup. Continue? (yes/no): yes
# 
# 🔄 Starting restore...
# Current keys: 1523
# 1️⃣  Flushing all Redis data...
# 2️⃣  Copying backup to Redis data directory...
# ✅ Backup file copied
# 3️⃣  Restarting Redis to load backup...
# ⚠️  NOTE: You may need to restart Redis manually:
#    docker-compose restart redis

# 4. Restart Redis
docker-compose start redis

# 5. Verify restore
docker-compose exec redis redis-cli DBSIZE
```

---

## S3 Configuration

### Prerequisites

- AWS account
- S3 bucket created
- IAM credentials with S3 write permissions

### IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-backup-bucket/*",
        "arn:aws:s3:::your-backup-bucket"
      ]
    }
  ]
}
```

### Environment Configuration

```bash
# In .env.production or docker-compose.yml
BACKUP_S3_BUCKET=my-zylin-backups
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Optional: Keep local backups after S3 upload
KEEP_LOCAL_BACKUP=true  # default: true
```

### S3 Bucket Structure

```
my-zylin-backups/
├── backups/
│   ├── postgres/
│   │   ├── postgres_zylin_20241210_020000.sql.gz
│   │   ├── postgres_zylin_20241209_020000.sql.gz
│   │   └── ...
│   └── redis/
│       ├── redis_20241210_030000.rdb.gz
│       ├── redis_20241209_030000.rdb.gz
│       └── ...
```

### S3 Lifecycle Policy (Cost Optimization)

```json
{
  "Rules": [
    {
      "Id": "Move to Glacier after 90 days",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

**Cost Savings:**
- Standard IA storage: $0.0125/GB/month (first 90 days)
- Glacier storage: $0.004/GB/month (after 90 days)
- Delete after 1 year (365 days)

---

## Monitoring

### Check Backup Status

```bash
# View backup logs
docker-compose logs -f backup

# Last 100 lines
docker-compose logs --tail=100 backup

# Filter for errors
docker-compose logs backup | grep -i error
```

### Verify Backup Files

```bash
# PostgreSQL backups
docker-compose exec backup sh -c "ls -lh /backups/postgres/ | tail -n 10"

# Redis backups
docker-compose exec backup sh -c "ls -lh /backups/redis/ | tail -n 10"

# Total backup size
docker-compose exec backup sh -c "du -sh /backups/*"
```

### Test Restore (Dry Run)

```bash
# Create test database from backup (doesn't affect production)
docker-compose exec backup sh -c "
  gunzip -c /backups/postgres/postgres_zylin_20241210_020000.sql.gz | head -n 100
"

# Verify Redis backup is readable
docker-compose exec backup sh -c "
  gunzip -t /backups/redis/redis_20241210_030000.rdb.gz && echo 'Backup file is valid'
"
```

---

## Backup Best Practices

### 1. Test Restores Regularly

```bash
# Monthly restore test (in staging environment)
# 1. Copy production backup to staging
# 2. Restore in staging
# 3. Verify data integrity
# 4. Document restore time
```

### 2. Monitor Backup Success

Set up alerts for:
- ❌ Backup failures
- ⚠️ Backup size anomalies (too small = incomplete)
- ⚠️ Missing scheduled backups
- ⚠️ S3 upload failures

### 3. Secure Backup Data

- 🔒 Encrypt backups at rest (S3 encryption enabled)
- 🔒 Restrict IAM permissions (least privilege)
- 🔒 Enable S3 versioning (protect against accidental deletion)
- 🔒 Use separate AWS account for backups (security isolation)

### 4. Document Recovery Procedures

Create a runbook:
1. **Detection**: How to detect data loss
2. **Assessment**: Determine extent of loss
3. **Decision**: Which backup to restore
4. **Execution**: Step-by-step restore
5. **Verification**: Data integrity checks
6. **Post-mortem**: Root cause analysis

### 5. Retention Strategy

| Backup Type | Retention | Why |
|-------------|-----------|-----|
| Daily | 30 days | Recent history |
| Weekly | 12 weeks | Medium-term recovery |
| Monthly | 12 months | Long-term compliance |
| Yearly | 7 years | Regulatory requirements |

**Implementation:**
```bash
# Daily: Keep last 30 days (automated)
BACKUP_RETENTION_DAYS=30

# Weekly/Monthly: Manual archive to separate S3 location
# Use S3 lifecycle policies to manage retention
```

---

## Disaster Recovery

### Scenario 1: Accidental Data Deletion

**Recovery Time Objective (RTO):** 15 minutes  
**Recovery Point Objective (RPO):** 24 hours (last daily backup)

```bash
# 1. Identify last good backup (before deletion)
docker-compose exec backup ls -lh /backups/postgres/

# 2. Stop services
docker-compose stop backend agent

# 3. Restore
docker-compose exec backup /scripts/restore-postgres.sh /backups/postgres/postgres_zylin_TIMESTAMP.sql.gz

# 4. Verify data
docker-compose exec postgres psql -U zylin_user -d zylin -c "SELECT COUNT(*) FROM customers;"

# 5. Restart services
docker-compose start backend agent
```

### Scenario 2: Database Corruption

**RTO:** 20 minutes  
**RPO:** 24 hours

```bash
# Similar to Scenario 1, but may need to:
# 1. Diagnose corruption extent
# 2. Consider partial restore if only one table affected
# 3. May need to restore from older backup if corruption went unnoticed
```

### Scenario 3: Complete Server Loss

**RTO:** 2 hours  
**RPO:** 24 hours

```bash
# 1. Provision new server
# 2. Install Docker and Docker Compose
# 3. Clone repository
# 4. Download backups from S3
aws s3 sync s3://my-zylin-backups/backups/ /backups/

# 5. Start services
docker-compose up -d

# 6. Restore PostgreSQL
docker-compose exec backup /scripts/restore-postgres.sh /backups/postgres/latest.sql.gz

# 7. Restore Redis
docker-compose exec backup /scripts/restore-redis.sh /backups/redis/latest.rdb.gz

# 8. Verify and test
```

---

## Troubleshooting

### Backup Script Fails

**Issue:** "Connection refused" error

**Solution:**
```bash
# Check database is running
docker-compose ps postgres

# Check network connectivity
docker-compose exec backup ping -c 3 postgres

# Check credentials
docker-compose exec backup env | grep DB_
```

### S3 Upload Fails

**Issue:** "Access Denied" error

**Solution:**
```bash
# Verify AWS credentials
docker-compose exec backup aws sts get-caller-identity

# Test S3 access
docker-compose exec backup aws s3 ls s3://my-zylin-backups/

# Check IAM permissions (see IAM Policy section)
```

### Backup File Too Small

**Issue:** Backup file is only a few KB (incomplete)

**Solution:**
```bash
# Check backup logs for errors
docker-compose logs backup | grep -i error

# Run backup manually with verbose output
docker-compose exec backup bash -x /scripts/backup-postgres.sh

# Verify database has data
docker-compose exec postgres psql -U zylin_user -d zylin -c "\dt"
```

### Restore Takes Too Long

**Issue:** Restore stuck or very slow

**Solution:**
```bash
# Check available disk space
docker-compose exec backup df -h

# Monitor restore progress (in another terminal)
docker-compose exec postgres psql -U zylin_user -d zylin -c "SELECT COUNT(*) FROM pg_stat_activity;"

# For large databases, consider:
# - Restore to separate database first
# - Use parallel restore (pg_restore with -j flag)
# - Tune PostgreSQL settings (maintenance_work_mem, max_wal_size)
```

---

## Cost Analysis

### Storage Costs

**Local Storage (Docker Volumes):**
- Free (uses host disk space)
- ~500 MB per daily backup (PostgreSQL + Redis)
- 30 days retention = ~15 GB total

**S3 Storage:**
- Standard-IA: $0.0125/GB/month
- 15 GB × $0.0125 = **$0.19/month**
- Plus: $0.01 per 1,000 PUT requests = ~$0.01/month
- **Total: ~$0.20/month**

**With Glacier Transition:**
- First 90 days: $0.19/month (Standard-IA)
- After 90 days: $0.06/month (Glacier)
- **Average: ~$0.10/month**

### Recommendations

For most deployments:
- ✅ **Local backups**: Enable (included by default)
- ✅ **S3 backups**: Enable for production (critical for DR)
- ✅ **Glacier transition**: Enable after 90 days
- ✅ **Delete after 1 year**: Enable (reduce costs)

**Total backup cost: ~$2-3/month** (local + S3 + Glacier)

---

## Next Steps

1. ✅ **Verify backup service is running**
   ```bash
   docker-compose ps backup
   ```

2. ✅ **Configure S3 for off-site backups** (recommended)
   ```bash
   # Edit .env.production
   BACKUP_S3_BUCKET=my-zylin-backups
   ```

3. ✅ **Test backup manually**
   ```bash
   docker-compose exec backup /scripts/backup-postgres.sh
   ```

4. ✅ **Schedule restore test** (monthly recommended)
   - Document in calendar
   - Create staging environment for testing
   - Time the restore process

5. ✅ **Set up monitoring alerts**
   - Backup failures
   - S3 upload failures
   - Disk space warnings

6. ✅ **Document recovery procedures**
   - Create team runbook
   - Assign roles and responsibilities
   - Define escalation procedures

---

## Summary

✅ **Automated daily backups** (PostgreSQL + Redis)  
✅ **30-day retention** (configurable)  
✅ **Optional S3 uploads** for disaster recovery  
✅ **Simple restore procedures** (one command)  
✅ **Redis AOF persistence** for near real-time durability  
✅ **Cost-effective** (~$2-3/month with S3)  
✅ **Production-ready** disaster recovery solution

**Status:** ✅ Fully implemented and tested  
**Maintenance:** Zero-touch (fully automated)  
**Recovery Time:** 15-20 minutes (from backup)
