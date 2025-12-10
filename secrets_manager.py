"""
AWS Secrets Manager Integration
Fetches secrets from AWS Secrets Manager for production deployments
"""
import json
import os
import sys
from typing import Dict, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Warning: boto3 not installed. Install with: pip install boto3")
    boto3 = None


class SecretsManager:
    """
    Manages secrets retrieval from AWS Secrets Manager.
    Falls back to environment variables if AWS is not configured.
    """
    
    def __init__(self, region_name: str = "us-east-1", use_aws: bool = True):
        """
        Initialize secrets manager.
        
        Args:
            region_name: AWS region for Secrets Manager
            use_aws: If False, only uses environment variables (for local dev)
        """
        self.region_name = region_name
        self.use_aws = use_aws and boto3 is not None
        self.client = None
        self._cache = {}
        
        if self.use_aws:
            try:
                self.client = boto3.client(
                    service_name='secretsmanager',
                    region_name=region_name
                )
                print(f"✅ AWS Secrets Manager connected (region: {region_name})")
            except Exception as e:
                print(f"⚠️  AWS Secrets Manager unavailable: {e}")
                print("   Falling back to environment variables")
                self.use_aws = False
    
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value from AWS Secrets Manager or environment.
        
        Args:
            secret_name: Name of the secret (e.g., 'zylin/openai-api-key')
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        # Check cache first
        if secret_name in self._cache:
            return self._cache[secret_name]
        
        # Try AWS Secrets Manager
        if self.use_aws:
            try:
                response = self.client.get_secret_value(SecretId=secret_name)
                
                # Parse secret value
                if 'SecretString' in response:
                    secret = response['SecretString']
                    
                    # Try to parse as JSON (for key-value secrets)
                    try:
                        secret_dict = json.loads(secret)
                        # If it's a dict with single key matching secret name, extract value
                        if len(secret_dict) == 1:
                            secret = list(secret_dict.values())[0]
                        else:
                            # Store entire dict in cache
                            self._cache[secret_name] = secret_dict
                            return secret_dict
                    except json.JSONDecodeError:
                        # Plain text secret
                        pass
                    
                    self._cache[secret_name] = secret
                    return secret
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ResourceNotFoundException':
                    print(f"⚠️  Secret '{secret_name}' not found in AWS")
                elif error_code == 'AccessDeniedException':
                    print(f"⚠️  Access denied to secret '{secret_name}'")
                else:
                    print(f"⚠️  Error retrieving secret '{secret_name}': {error_code}")
            except Exception as e:
                print(f"⚠️  Unexpected error retrieving '{secret_name}': {e}")
        
        # Fallback to environment variable
        env_var = secret_name.split('/')[-1].upper().replace('-', '_')
        value = os.getenv(env_var, default)
        
        if value:
            self._cache[secret_name] = value
        
        return value
    
    def get_secret_dict(self, secret_name: str) -> Dict[str, str]:
        """
        Get a secret that contains multiple key-value pairs (JSON format).
        
        Args:
            secret_name: Name of the secret containing JSON
            
        Returns:
            Dictionary of secret values
        """
        secret = self.get_secret(secret_name)
        
        if isinstance(secret, dict):
            return secret
        
        if isinstance(secret, str):
            try:
                return json.loads(secret)
            except json.JSONDecodeError:
                return {'value': secret}
        
        return {}
    
    def load_secrets_to_env(self, secret_mappings: Dict[str, str]):
        """
        Load multiple secrets into environment variables.
        
        Args:
            secret_mappings: Dict mapping env var names to secret names
                Example: {
                    'OPENAI_API_KEY': 'zylin/openai-api-key',
                    'DATABASE_URL': 'zylin/database-url'
                }
        """
        loaded_count = 0
        failed_count = 0
        
        for env_var, secret_name in secret_mappings.items():
            value = self.get_secret(secret_name)
            
            if value:
                os.environ[env_var] = value
                loaded_count += 1
                print(f"✅ Loaded {env_var}")
            else:
                failed_count += 1
                print(f"❌ Failed to load {env_var} from {secret_name}")
        
        print(f"\n📊 Secrets loaded: {loaded_count}/{loaded_count + failed_count}")
        return loaded_count, failed_count


def load_production_secrets(region: str = "us-east-1") -> SecretsManager:
    """
    Load all production secrets for Zylin AI.
    
    Args:
        region: AWS region for Secrets Manager
        
    Returns:
        Configured SecretsManager instance
    """
    # Check if we should use AWS (production) or environment variables (dev)
    use_aws = os.getenv('USE_AWS_SECRETS', 'false').lower() == 'true'
    
    if not use_aws:
        print("🔧 Development mode: Using environment variables")
        print("   Set USE_AWS_SECRETS=true to use AWS Secrets Manager\n")
    
    manager = SecretsManager(region_name=region, use_aws=use_aws)
    
    # Define all secrets to load
    secret_mappings = {
        # Database
        'DATABASE_URL': 'zylin/database-url',
        'DB_PASSWORD': 'zylin/db-password',
        
        # APIs
        'OPENAI_API_KEY': 'zylin/openai-api-key',
        'ASSEMBLYAI_API_KEY': 'zylin/assemblyai-api-key',
        'ELEVENLABS_API_KEY': 'zylin/elevenlabs-api-key',
        
        # LiveKit
        'LIVEKIT_URL': 'zylin/livekit-url',
        'LIVEKIT_API_KEY': 'zylin/livekit-api-key',
        'LIVEKIT_API_SECRET': 'zylin/livekit-api-secret',
        
        # Security
        'JWT_SECRET_KEY': 'zylin/jwt-secret-key',
        'API_KEY_SALT': 'zylin/api-key-salt',
        
        # Email
        'SENDGRID_API_KEY': 'zylin/sendgrid-api-key',
        
        # Optional: Azure TTS
        'AZURE_SPEECH_KEY': 'zylin/azure-speech-key',
        
        # Optional: Monitoring
        'SENTRY_DSN': 'zylin/sentry-dsn',
    }
    
    print("🔐 Loading secrets...\n")
    manager.load_secrets_to_env(secret_mappings)
    
    return manager


def create_aws_secrets(region: str = "us-east-1", dry_run: bool = True):
    """
    Create secrets in AWS Secrets Manager from current environment variables.
    
    Args:
        region: AWS region for Secrets Manager
        dry_run: If True, only prints what would be created
    """
    if not boto3:
        print("❌ boto3 not installed. Install with: pip install boto3")
        return
    
    from dotenv import load_dotenv
    load_dotenv()
    
    client = boto3.client('secretsmanager', region_name=region)
    
    secrets_to_create = {
        'zylin/database-url': os.getenv('DATABASE_URL'),
        'zylin/db-password': os.getenv('DB_PASSWORD'),
        'zylin/openai-api-key': os.getenv('OPENAI_API_KEY'),
        'zylin/assemblyai-api-key': os.getenv('ASSEMBLYAI_API_KEY'),
        'zylin/elevenlabs-api-key': os.getenv('TTS_API_KEY'),
        'zylin/livekit-url': os.getenv('LIVEKIT_URL'),
        'zylin/livekit-api-key': os.getenv('LIVEKIT_API_KEY'),
        'zylin/livekit-api-secret': os.getenv('LIVEKIT_API_SECRET'),
        'zylin/jwt-secret-key': os.getenv('JWT_SECRET_KEY'),
        'zylin/api-key-salt': os.getenv('API_KEY_SALT'),
        'zylin/sendgrid-api-key': os.getenv('SENDGRID_API_KEY'),
        'zylin/azure-speech-key': os.getenv('AZURE_SPEECH_KEY'),
        'zylin/sentry-dsn': os.getenv('SENTRY_DSN'),
    }
    
    print(f"{'🔍 DRY RUN - ' if dry_run else '🚀 CREATING '} AWS Secrets in {region}")
    print("=" * 60)
    
    created = 0
    skipped = 0
    
    for secret_name, secret_value in secrets_to_create.items():
        if not secret_value:
            print(f"⏭️  Skipping {secret_name} (not set in environment)")
            skipped += 1
            continue
        
        if dry_run:
            print(f"📝 Would create: {secret_name}")
            print(f"   Value: {secret_value[:10]}...{secret_value[-4:] if len(secret_value) > 14 else ''}")
        else:
            try:
                client.create_secret(
                    Name=secret_name,
                    SecretString=secret_value,
                    Description=f"Zylin AI - {secret_name.split('/')[-1]}"
                )
                print(f"✅ Created: {secret_name}")
                created += 1
            except client.exceptions.ResourceExistsException:
                # Update existing secret
                client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_value
                )
                print(f"🔄 Updated: {secret_name}")
                created += 1
            except Exception as e:
                print(f"❌ Failed to create {secret_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Summary: {created} created/updated, {skipped} skipped")
    
    if dry_run:
        print("\n💡 To actually create secrets, run:")
        print("   python -c \"from secrets_manager import create_aws_secrets; create_aws_secrets(dry_run=False)\"")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AWS Secrets Manager for Zylin AI")
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--create', action='store_true', help='Create secrets from .env file')
    parser.add_argument('--no-dry-run', action='store_true', help='Actually create secrets (not dry run)')
    parser.add_argument('--test', action='store_true', help='Test secret retrieval')
    
    args = parser.parse_args()
    
    if args.create:
        create_aws_secrets(region=args.region, dry_run=not args.no_dry_run)
    elif args.test:
        manager = load_production_secrets(region=args.region)
        print("\n✅ Secrets manager initialized successfully")
    else:
        print("Usage:")
        print("  --create         Create secrets from .env file (dry run)")
        print("  --no-dry-run     Actually create secrets")
        print("  --test           Test secret retrieval")
        print("  --region REGION  AWS region (default: us-east-1)")
