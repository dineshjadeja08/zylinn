# Secrets Management Guide

## Overview

Zylin AI supports **three methods** for managing secrets in production:

1. **AWS Secrets Manager** (recommended for AWS deployments)
2. **HashiCorp Vault** (recommended for on-premise or multi-cloud)
3. **Environment Variables** (development only)

This guide covers setting up and using secrets management for production deployments.

## Why Use Secrets Management?

**Problems with .env files:**
- ❌ Secrets committed to git (security risk)
- ❌ Manual rotation across servers
- ❌ No audit trail of access
- ❌ Difficult to revoke compromised keys
- ❌ No encryption at rest

**Benefits of secrets management:**
- ✅ Secrets never touch git repository
- ✅ Centralized secrets storage
- ✅ Automatic encryption at rest
- ✅ Audit logging of all access
- ✅ Easy rotation and revocation
- ✅ IAM/RBAC access control
- ✅ Automatic injection into applications

---

## Option 1: AWS Secrets Manager

### Prerequisites

- AWS account
- AWS CLI configured (`aws configure`)
- IAM permissions for Secrets Manager

### Step 1: Install Dependencies

```bash
pip install boto3
```

### Step 2: Create Secrets from .env File

```bash
# Dry run (see what would be created)
python secrets_manager.py --create

# Actually create secrets
python secrets_manager.py --create --no-dry-run --region us-east-1
```

This creates secrets in AWS Secrets Manager:
- `zylin/database-url`
- `zylin/openai-api-key`
- `zylin/elevenlabs-api-key`
- `zylin/livekit-api-key`
- `zylin/jwt-secret-key`
- And more...

### Step 3: Configure IAM Permissions

Create IAM policy for your application:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:zylin/*"
    }
  ]
}
```

Attach policy to:
- EC2 instance role
- ECS task role
- Lambda execution role

### Step 4: Update Docker Compose / Deployment

**Option A: Use startup script (recommended)**

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - SECRETS_PROVIDER=aws
      - AWS_REGION=us-east-1
    command: python start_production.py backend
```

**Option B: Pre-load secrets before starting**

```bash
# In your deployment script
export SECRETS_PROVIDER=aws
export AWS_REGION=us-east-1
python secrets_manager.py --test  # Load secrets to env
python -m backend.app  # Start app with loaded secrets
```

### Step 5: Validate

```bash
# Test secrets retrieval
python secrets_manager.py --test

# Validate all critical secrets
python start_production.py validate
```

### Cost Estimation

AWS Secrets Manager pricing (us-east-1):
- **$0.40** per secret per month
- **$0.05** per 10,000 API calls

**Zylin AI example:**
- 13 secrets × $0.40 = $5.20/month
- ~100,000 API calls/month = $0.50/month
- **Total: ~$6/month**

---

## Option 2: HashiCorp Vault

### Prerequisites

- Vault server running (self-hosted or cloud)
- Vault token with read permissions
- `VAULT_ADDR` and `VAULT_TOKEN` configured

### Step 1: Install Vault (if self-hosting)

```bash
# Docker Compose
docker run -d --name=vault \
  -p 8200:8200 \
  --cap-add=IPC_LOCK \
  vault server -dev -dev-root-token-id="root"
```

**Production**: Use Vault in HA mode with proper storage backend

### Step 2: Install Dependencies

```bash
pip install hvac
```

### Step 3: Enable KV Secrets Engine

```bash
# Login to Vault
export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='root'

# Enable KV v2 engine (if not already enabled)
vault secrets enable -path=secret kv-v2
```

### Step 4: Create Secrets from .env File

```bash
# Dry run
python vault_manager.py --create

# Actually create secrets
python vault_manager.py --create --no-dry-run
```

This creates secrets in Vault:
- `secret/zylin/database` (url, password)
- `secret/zylin/openai` (api_key)
- `secret/zylin/elevenlabs` (api_key)
- `secret/zylin/livekit` (url, api_key, api_secret)
- `secret/zylin/security` (jwt_secret, api_key_salt)
- And more...

### Step 5: Update Docker Compose / Deployment

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - SECRETS_PROVIDER=vault
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}  # Or use AppRole/Kubernetes auth
    command: python start_production.py backend
```

### Step 6: Validate

```bash
# Test secrets retrieval
python vault_manager.py --test

# Validate all critical secrets
python start_production.py validate
```

### Cost Estimation

HashiCorp Vault:
- **Self-hosted**: Free (open source) + infrastructure costs
- **HCP Vault** (cloud): $0.03/hour = ~$22/month (Starter)

---

## Option 3: Environment Variables (Development Only)

**⚠️ Not recommended for production**

```bash
# Simply use .env file
cp .env.example .env
# Edit .env with real credentials

# Start services
python start_production.py backend
```

---

## Production Startup Script

The `start_production.py` script handles secrets loading automatically:

```bash
# Backend with AWS Secrets Manager
SECRETS_PROVIDER=aws python start_production.py backend

# Agent with HashiCorp Vault
SECRETS_PROVIDER=vault python start_production.py agent

# Validate secrets only
SECRETS_PROVIDER=aws python start_production.py validate
```

### How It Works

```python
1. Read SECRETS_PROVIDER environment variable
   ├─ aws → Load from AWS Secrets Manager
   ├─ vault → Load from HashiCorp Vault
   └─ env → Load from .env file (dev)

2. Fetch all secrets and inject into os.environ
   ├─ DATABASE_URL
   ├─ OPENAI_API_KEY
   ├─ JWT_SECRET_KEY
   └─ ...

3. Validate critical secrets are present
   └─ Exit if any missing

4. Start requested service (backend or agent)
```

---

## Secrets List

### Critical Secrets (Required)

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `LIVEKIT_URL` | LiveKit WebSocket URL | `wss://your-livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit API key | `APIxxxx...` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `secret...` |
| `JWT_SECRET_KEY` | JWT signing key | Random 32+ characters |

### Optional Secrets

| Secret Name | Description | Required For |
|-------------|-------------|--------------|
| `ASSEMBLYAI_API_KEY` | AssemblyAI STT | Production STT |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS | Production TTS |
| `SENDGRID_API_KEY` | SendGrid email | Email verification |
| `API_KEY_SALT` | API key hashing salt | API authentication |
| `AZURE_SPEECH_KEY` | Azure TTS | Azure TTS fallback |
| `SENTRY_DSN` | Sentry error tracking | Error monitoring |

---

## Security Best Practices

### 1. Never Commit Secrets

Add to `.gitignore`:
```
.env
.env.local
.env.production
secrets.json
vault-token
```

### 2. Rotate Secrets Regularly

**AWS Secrets Manager:**
```bash
aws secretsmanager rotate-secret \
  --secret-id zylin/openai-api-key \
  --rotation-lambda-arn <lambda-arn>
```

**HashiCorp Vault:**
```bash
# Generate new secret
NEW_KEY=$(openssl rand -base64 32)

# Update secret
vault kv put secret/zylin/security jwt_secret="$NEW_KEY"
```

### 3. Use Least Privilege IAM/Policies

**AWS**: Grant only `GetSecretValue` for specific secrets
**Vault**: Use policies limiting access to `zylin/*` path only

### 4. Enable Audit Logging

**AWS CloudTrail**: Log all Secrets Manager API calls
**Vault Audit**: Enable file or syslog audit device

### 5. Use Short-Lived Tokens

**Vault**: Use AppRole or Kubernetes auth (not root tokens)
**AWS**: Use IAM roles (not long-lived access keys)

---

## Troubleshooting

### AWS Secrets Manager

**Issue**: `AccessDeniedException`

**Solution**: Check IAM permissions
```bash
aws iam get-role-policy \
  --role-name your-role \
  --policy-name SecretsManagerAccess
```

**Issue**: `ResourceNotFoundException`

**Solution**: Create missing secrets
```bash
aws secretsmanager create-secret \
  --name zylin/openai-api-key \
  --secret-string "sk-..."
```

### HashiCorp Vault

**Issue**: `Forbidden` or `Permission denied`

**Solution**: Check Vault policy
```bash
vault policy read zylin-policy
```

**Issue**: `Connection refused`

**Solution**: Check Vault is running and VAULT_ADDR is correct
```bash
curl $VAULT_ADDR/v1/sys/health
```

### General

**Issue**: Application can't find secrets

**Solution**: Enable debug logging
```python
import structlog
structlog.configure(
    processors=[structlog.processors.add_log_level],
)

# Check what was loaded
import os
print("DATABASE_URL:", os.getenv('DATABASE_URL')[:20] + "...")
```

---

## Migration Guide

### From .env to AWS Secrets Manager

```bash
# 1. Backup current .env
cp .env .env.backup

# 2. Create secrets in AWS
python secrets_manager.py --create --no-dry-run

# 3. Test retrieval
python secrets_manager.py --test

# 4. Update deployment to use AWS
export SECRETS_PROVIDER=aws

# 5. Validate
python start_production.py validate

# 6. Deploy
docker-compose up -d

# 7. Remove .env from servers (keep backup)
mv .env .env.removed
```

### From .env to HashiCorp Vault

```bash
# 1. Backup current .env
cp .env .env.backup

# 2. Start Vault (if not running)
docker-compose up -d vault

# 3. Create secrets in Vault
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root
python vault_manager.py --create --no-dry-run

# 4. Test retrieval
python vault_manager.py --test

# 5. Update deployment
export SECRETS_PROVIDER=vault

# 6. Validate
python start_production.py validate

# 7. Deploy
docker-compose up -d

# 8. Remove .env from servers
mv .env .env.removed
```

---

## Docker Compose Integration

### With AWS Secrets Manager

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    environment:
      - SECRETS_PROVIDER=aws
      - AWS_REGION=us-east-1
      # AWS credentials via IAM role or environment
    command: python /app/start_production.py backend
    
  agent:
    build: ./agent
    environment:
      - SECRETS_PROVIDER=aws
      - AWS_REGION=us-east-1
    command: python /app/start_production.py agent
```

### With HashiCorp Vault

```yaml
version: '3.8'

services:
  vault:
    image: vault:latest
    ports:
      - "8200:8200"
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=root
    cap_add:
      - IPC_LOCK
      
  backend:
    build: ./backend
    depends_on:
      - vault
    environment:
      - SECRETS_PROVIDER=vault
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}
    command: python /app/start_production.py backend
```

---

## Monitoring & Alerts

### AWS CloudWatch

Monitor Secrets Manager API usage:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/SecretsManager \
  --metric-name SecretRetrievalCount \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-31T23:59:59Z \
  --period 86400 \
  --statistics Sum
```

### Vault Audit Logs

Check who accessed secrets:
```bash
vault audit enable file file_path=/vault/logs/audit.log

# View logs
tail -f /vault/logs/audit.log | jq
```

---

## Next Steps

1. ✅ **Choose secrets provider** (AWS or Vault)
2. ✅ **Install dependencies** (`boto3` or `hvac`)
3. ✅ **Create secrets** from .env file
4. ✅ **Configure IAM/policies** for access control
5. ✅ **Update deployment** to use secrets manager
6. ✅ **Test thoroughly** in staging environment
7. ✅ **Remove .env files** from production servers
8. ✅ **Set up rotation schedule** (90 days recommended)
9. ✅ **Enable audit logging** for compliance
10. ✅ **Document secrets** in team wiki

---

## Support

- **AWS Secrets Manager**: https://docs.aws.amazon.com/secretsmanager/
- **HashiCorp Vault**: https://www.vaultproject.io/docs
- **boto3 SDK**: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **hvac SDK**: https://hvac.readthedocs.io/

---

**Status**: ✅ Production-ready  
**Security Level**: 🔒 Enterprise-grade  
**Recommended For**: All production deployments
