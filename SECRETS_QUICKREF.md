# Secrets Management - Quick Reference

## Installation

```bash
# AWS Secrets Manager
pip install boto3

# HashiCorp Vault
pip install hvac
```

## Create Secrets

```bash
# AWS (dry run)
python secrets_manager.py --create

# AWS (create for real)
python secrets_manager.py --create --no-dry-run --region us-east-1

# Vault (dry run)
python vault_manager.py --create

# Vault (create for real)
python vault_manager.py --create --no-dry-run
```

## Test Secrets

```bash
# AWS
python secrets_manager.py --test

# Vault
python vault_manager.py --test

# Validate all
python start_production.py validate
```

## Start Services

```bash
# Development (use .env)
python start_production.py backend

# Production with AWS
SECRETS_PROVIDER=aws python start_production.py backend

# Production with Vault
SECRETS_PROVIDER=vault python start_production.py agent
```

## Docker Compose

```yaml
# AWS Secrets Manager
services:
  backend:
    environment:
      - SECRETS_PROVIDER=aws
      - AWS_REGION=us-east-1
    command: python start_production.py backend

# HashiCorp Vault
services:
  backend:
    environment:
      - SECRETS_PROVIDER=vault
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}
    command: python start_production.py backend
```

## Environment Variables

```bash
# Choose provider
export SECRETS_PROVIDER=aws  # or vault or env

# AWS
export AWS_REGION=us-east-1
# (AWS credentials via IAM role or ~/.aws/credentials)

# Vault
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=your_token_here
```

## Secrets List

### Critical
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `JWT_SECRET_KEY`

### Optional
- `ASSEMBLYAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `SENDGRID_API_KEY`
- `API_KEY_SALT`
- `AZURE_SPEECH_KEY`
- `SENTRY_DSN`

## IAM Policy (AWS)

```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": "arn:aws:secretsmanager:*:*:secret:zylin/*"
}
```

## Vault Policy

```hcl
path "secret/data/zylin/*" {
  capabilities = ["read", "list"]
}
```

## Troubleshooting

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check Vault connection
curl $VAULT_ADDR/v1/sys/health

# Debug secrets loading
python -c "from secrets_manager import load_production_secrets; load_production_secrets()"

# Check loaded env vars
env | grep -E 'OPENAI|DATABASE|LIVEKIT'
```

## Cost

- **AWS**: ~$6/month (13 secrets + API calls)
- **Vault self-hosted**: Free + infrastructure
- **HCP Vault**: ~$22/month (Starter tier)

## Security Checklist

- [ ] Secrets created in manager (not .env)
- [ ] IAM/policies configured (least privilege)
- [ ] Audit logging enabled
- [ ] .env files removed from production
- [ ] Rotation schedule set (90 days)
- [ ] Team documented in wiki
- [ ] Tested in staging first

---

**See**: `SECRETS_MANAGEMENT.md` for complete guide
