"""
HashiCorp Vault Integration
Alternative to AWS Secrets Manager for on-premise or multi-cloud deployments
"""
import os
import sys
from typing import Dict, Optional

try:
    import hvac
except ImportError:
    print("Warning: hvac not installed. Install with: pip install hvac")
    hvac = None


class VaultManager:
    """
    Manages secrets retrieval from HashiCorp Vault.
    Falls back to environment variables if Vault is not configured.
    """
    
    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        mount_point: str = "secret",
        use_vault: bool = True
    ):
        """
        Initialize Vault manager.
        
        Args:
            vault_addr: Vault server address (e.g., http://localhost:8200)
            vault_token: Vault authentication token
            mount_point: KV secrets engine mount point
            use_vault: If False, only uses environment variables
        """
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://localhost:8200')
        self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
        self.mount_point = mount_point
        self.use_vault = use_vault and hvac is not None and self.vault_token
        self.client = None
        self._cache = {}
        
        if self.use_vault:
            try:
                self.client = hvac.Client(
                    url=self.vault_addr,
                    token=self.vault_token
                )
                
                # Verify authentication
                if self.client.is_authenticated():
                    print(f"✅ HashiCorp Vault connected ({self.vault_addr})")
                else:
                    print("⚠️  Vault authentication failed")
                    self.use_vault = False
                    
            except Exception as e:
                print(f"⚠️  HashiCorp Vault unavailable: {e}")
                print("   Falling back to environment variables")
                self.use_vault = False
    
    def get_secret(self, secret_path: str, key: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value from Vault or environment.
        
        Args:
            secret_path: Path to secret (e.g., 'zylin/openai')
            key: Key within secret (e.g., 'api_key'). If None, returns full secret dict
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        cache_key = f"{secret_path}:{key}" if key else secret_path
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Try Vault
        if self.use_vault:
            try:
                # Read secret from KV v2 engine
                secret_response = self.client.secrets.kv.v2.read_secret_version(
                    path=secret_path,
                    mount_point=self.mount_point
                )
                
                secret_data = secret_response['data']['data']
                
                if key:
                    # Return specific key
                    value = secret_data.get(key, default)
                else:
                    # Return entire secret
                    value = secret_data
                
                self._cache[cache_key] = value
                return value
                
            except hvac.exceptions.InvalidPath:
                print(f"⚠️  Secret '{secret_path}' not found in Vault")
            except hvac.exceptions.Forbidden:
                print(f"⚠️  Access denied to secret '{secret_path}'")
            except Exception as e:
                print(f"⚠️  Error retrieving secret '{secret_path}': {e}")
        
        # Fallback to environment variable
        if key:
            env_var = key.upper().replace('-', '_')
        else:
            env_var = secret_path.split('/')[-1].upper().replace('-', '_')
        
        value = os.getenv(env_var, default)
        
        if value:
            self._cache[cache_key] = value
        
        return value
    
    def get_secret_dict(self, secret_path: str) -> Dict[str, str]:
        """
        Get all key-value pairs from a secret.
        
        Args:
            secret_path: Path to secret
            
        Returns:
            Dictionary of secret values
        """
        secret = self.get_secret(secret_path)
        
        if isinstance(secret, dict):
            return secret
        
        return {}
    
    def load_secrets_to_env(self, secret_mappings: Dict[str, tuple]):
        """
        Load multiple secrets into environment variables.
        
        Args:
            secret_mappings: Dict mapping env var names to (path, key) tuples
                Example: {
                    'OPENAI_API_KEY': ('zylin/openai', 'api_key'),
                    'DATABASE_URL': ('zylin/database', 'url')
                }
        """
        loaded_count = 0
        failed_count = 0
        
        for env_var, (secret_path, key) in secret_mappings.items():
            value = self.get_secret(secret_path, key)
            
            if value:
                os.environ[env_var] = value
                loaded_count += 1
                print(f"✅ Loaded {env_var}")
            else:
                failed_count += 1
                print(f"❌ Failed to load {env_var} from {secret_path}/{key}")
        
        print(f"\n📊 Secrets loaded: {loaded_count}/{loaded_count + failed_count}")
        return loaded_count, failed_count


def load_production_secrets_vault() -> VaultManager:
    """
    Load all production secrets from HashiCorp Vault.
    
    Returns:
        Configured VaultManager instance
    """
    # Check if we should use Vault (production) or environment variables (dev)
    use_vault = os.getenv('USE_VAULT', 'false').lower() == 'true'
    
    if not use_vault:
        print("🔧 Development mode: Using environment variables")
        print("   Set USE_VAULT=true to use HashiCorp Vault\n")
    
    manager = VaultManager(use_vault=use_vault)
    
    # Define all secrets to load
    # Format: env_var: (vault_path, key)
    secret_mappings = {
        # Database
        'DATABASE_URL': ('zylin/database', 'url'),
        'DB_PASSWORD': ('zylin/database', 'password'),
        
        # APIs
        'OPENAI_API_KEY': ('zylin/openai', 'api_key'),
        'ASSEMBLYAI_API_KEY': ('zylin/assemblyai', 'api_key'),
        'ELEVENLABS_API_KEY': ('zylin/elevenlabs', 'api_key'),
        
        # LiveKit
        'LIVEKIT_URL': ('zylin/livekit', 'url'),
        'LIVEKIT_API_KEY': ('zylin/livekit', 'api_key'),
        'LIVEKIT_API_SECRET': ('zylin/livekit', 'api_secret'),
        
        # Security
        'JWT_SECRET_KEY': ('zylin/security', 'jwt_secret'),
        'API_KEY_SALT': ('zylin/security', 'api_key_salt'),
        
        # Email
        'SENDGRID_API_KEY': ('zylin/sendgrid', 'api_key'),
        
        # Optional: Azure TTS
        'AZURE_SPEECH_KEY': ('zylin/azure', 'speech_key'),
        
        # Optional: Monitoring
        'SENTRY_DSN': ('zylin/sentry', 'dsn'),
    }
    
    print("🔐 Loading secrets from Vault...\n")
    manager.load_secrets_to_env(secret_mappings)
    
    return manager


def create_vault_secrets(dry_run: bool = True):
    """
    Create secrets in HashiCorp Vault from current environment variables.
    
    Args:
        dry_run: If True, only prints what would be created
    """
    if not hvac:
        print("❌ hvac not installed. Install with: pip install hvac")
        return
    
    from dotenv import load_dotenv
    load_dotenv()
    
    vault_addr = os.getenv('VAULT_ADDR', 'http://localhost:8200')
    vault_token = os.getenv('VAULT_TOKEN')
    
    if not vault_token:
        print("❌ VAULT_TOKEN not set. Cannot authenticate to Vault.")
        return
    
    client = hvac.Client(url=vault_addr, token=vault_token)
    
    if not client.is_authenticated():
        print("❌ Vault authentication failed")
        return
    
    secrets_to_create = {
        'zylin/database': {
            'url': os.getenv('DATABASE_URL'),
            'password': os.getenv('DB_PASSWORD'),
        },
        'zylin/openai': {
            'api_key': os.getenv('OPENAI_API_KEY'),
        },
        'zylin/assemblyai': {
            'api_key': os.getenv('ASSEMBLYAI_API_KEY'),
        },
        'zylin/elevenlabs': {
            'api_key': os.getenv('TTS_API_KEY'),
        },
        'zylin/livekit': {
            'url': os.getenv('LIVEKIT_URL'),
            'api_key': os.getenv('LIVEKIT_API_KEY'),
            'api_secret': os.getenv('LIVEKIT_API_SECRET'),
        },
        'zylin/security': {
            'jwt_secret': os.getenv('JWT_SECRET_KEY'),
            'api_key_salt': os.getenv('API_KEY_SALT'),
        },
        'zylin/sendgrid': {
            'api_key': os.getenv('SENDGRID_API_KEY'),
        },
        'zylin/azure': {
            'speech_key': os.getenv('AZURE_SPEECH_KEY'),
        },
        'zylin/sentry': {
            'dsn': os.getenv('SENTRY_DSN'),
        },
    }
    
    print(f"{'🔍 DRY RUN - ' if dry_run else '🚀 CREATING '} Vault Secrets at {vault_addr}")
    print("=" * 60)
    
    created = 0
    skipped = 0
    
    for secret_path, secret_data in secrets_to_create.items():
        # Filter out None values
        filtered_data = {k: v for k, v in secret_data.items() if v is not None}
        
        if not filtered_data:
            print(f"⏭️  Skipping {secret_path} (no values set)")
            skipped += 1
            continue
        
        if dry_run:
            print(f"📝 Would create: {secret_path}")
            for key, value in filtered_data.items():
                print(f"   {key}: {value[:10]}...{value[-4:] if len(value) > 14 else ''}")
        else:
            try:
                client.secrets.kv.v2.create_or_update_secret(
                    path=secret_path,
                    secret=filtered_data,
                    mount_point='secret'
                )
                print(f"✅ Created: {secret_path} ({len(filtered_data)} keys)")
                created += 1
            except Exception as e:
                print(f"❌ Failed to create {secret_path}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Summary: {created} created/updated, {skipped} skipped")
    
    if dry_run:
        print("\n💡 To actually create secrets, run:")
        print("   python -c \"from vault_manager import create_vault_secrets; create_vault_secrets(dry_run=False)\"")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HashiCorp Vault Manager for Zylin AI")
    parser.add_argument('--create', action='store_true', help='Create secrets from .env file')
    parser.add_argument('--no-dry-run', action='store_true', help='Actually create secrets (not dry run)')
    parser.add_argument('--test', action='store_true', help='Test secret retrieval')
    
    args = parser.parse_args()
    
    if args.create:
        create_vault_secrets(dry_run=not args.no_dry_run)
    elif args.test:
        manager = load_production_secrets_vault()
        print("\n✅ Vault manager initialized successfully")
    else:
        print("Usage:")
        print("  --create         Create secrets from .env file (dry run)")
        print("  --no-dry-run     Actually create secrets")
        print("  --test           Test secret retrieval")
