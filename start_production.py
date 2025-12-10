#!/usr/bin/env python3
"""
Production startup script with secrets management
Loads secrets from AWS Secrets Manager or HashiCorp Vault before starting the application
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def load_secrets():
    """Load secrets from configured secrets manager"""
    secrets_provider = os.getenv('SECRETS_PROVIDER', 'env').lower()
    
    print("=" * 60)
    print("🔐 Zylin AI - Secrets Loading")
    print("=" * 60)
    print(f"Provider: {secrets_provider}\n")
    
    if secrets_provider == 'aws':
        # Use AWS Secrets Manager
        try:
            from secrets_manager import load_production_secrets
            
            region = os.getenv('AWS_REGION', 'us-east-1')
            os.environ['USE_AWS_SECRETS'] = 'true'
            
            print(f"🔒 Using AWS Secrets Manager (region: {region})")
            manager = load_production_secrets(region=region)
            
            return True
            
        except ImportError:
            print("❌ secrets_manager.py not found or boto3 not installed")
            print("   Install: pip install boto3")
            return False
        except Exception as e:
            print(f"❌ Failed to load secrets from AWS: {e}")
            return False
    
    elif secrets_provider == 'vault':
        # Use HashiCorp Vault
        try:
            from vault_manager import load_production_secrets_vault
            
            vault_addr = os.getenv('VAULT_ADDR', 'http://localhost:8200')
            os.environ['USE_VAULT'] = 'true'
            
            print(f"🔒 Using HashiCorp Vault ({vault_addr})")
            manager = load_production_secrets_vault()
            
            return True
            
        except ImportError:
            print("❌ vault_manager.py not found or hvac not installed")
            print("   Install: pip install hvac")
            return False
        except Exception as e:
            print(f"❌ Failed to load secrets from Vault: {e}")
            return False
    
    else:
        # Use environment variables (development mode)
        print("🔧 Using environment variables (.env file)")
        print("   Set SECRETS_PROVIDER=aws or SECRETS_PROVIDER=vault for production\n")
        
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Loaded .env file")
            return True
        except ImportError:
            print("⚠️  python-dotenv not installed. Using existing environment variables")
            return True


def validate_critical_secrets():
    """Validate that critical secrets are loaded"""
    critical_secrets = [
        'DATABASE_URL',
        'OPENAI_API_KEY',
        'LIVEKIT_URL',
        'LIVEKIT_API_KEY',
        'LIVEKIT_API_SECRET',
        'JWT_SECRET_KEY',
    ]
    
    print("\n" + "=" * 60)
    print("🔍 Validating Critical Secrets")
    print("=" * 60)
    
    missing = []
    for secret in critical_secrets:
        value = os.getenv(secret)
        if value:
            # Show first 4 and last 4 characters
            masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            print(f"✅ {secret}: {masked}")
        else:
            print(f"❌ {secret}: NOT SET")
            missing.append(secret)
    
    if missing:
        print(f"\n❌ Missing {len(missing)} critical secrets:")
        for secret in missing:
            print(f"   - {secret}")
        return False
    
    print(f"\n✅ All {len(critical_secrets)} critical secrets validated")
    return True


def start_backend():
    """Start the FastAPI backend server"""
    print("\n" + "=" * 60)
    print("🚀 Starting Backend Service")
    print("=" * 60)
    
    host = os.getenv('BACKEND_HOST', '0.0.0.0')
    port = int(os.getenv('BACKEND_PORT', 8000))
    reload = os.getenv('BACKEND_RELOAD', 'false').lower() == 'true'
    
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print()
    
    # Start uvicorn
    try:
        import uvicorn
        from backend.app import app
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        print("❌ uvicorn or backend.app not found")
        print("   Install: pip install uvicorn")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        sys.exit(1)


def start_agent():
    """Start the voice agent"""
    print("\n" + "=" * 60)
    print("🚀 Starting Agent Service")
    print("=" * 60)
    
    try:
        # Import and run the agent
        import asyncio
        from run_persistent_agent import main
        
        asyncio.run(main())
        
    except ImportError:
        print("❌ run_persistent_agent.py not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start agent: {e}")
        sys.exit(1)


def main():
    """Main startup orchestration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zylin AI Production Startup")
    parser.add_argument('service', choices=['backend', 'agent', 'validate'], 
                       help='Service to start or validate secrets only')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip secrets validation (not recommended)')
    
    args = parser.parse_args()
    
    # Load secrets
    if not load_secrets():
        print("\n❌ Failed to load secrets. Exiting.")
        sys.exit(1)
    
    # Validate secrets
    if not args.skip_validation:
        if not validate_critical_secrets():
            print("\n❌ Secrets validation failed. Exiting.")
            sys.exit(1)
    
    # Start requested service
    if args.service == 'validate':
        print("\n✅ Validation complete. Secrets are properly configured.")
        sys.exit(0)
    elif args.service == 'backend':
        start_backend()
    elif args.service == 'agent':
        start_agent()


if __name__ == "__main__":
    main()
