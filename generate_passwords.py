"""
Password Generation and Rotation Script
Generates secure passwords and updates configuration files
"""
import os
import secrets
import string
import hashlib
from datetime import datetime


def generate_password(length=32, special_chars=True):
    """Generate a cryptographically secure random password"""
    alphabet = string.ascii_letters + string.digits
    if special_chars:
        alphabet += string.punctuation
    
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_api_key():
    """Generate an API key in standard format"""
    return f"sk_{secrets.token_urlsafe(32)}"


def hash_password(password, salt=None):
    """Hash password with SHA-256 (for demonstration)"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hashed.hex()}"


def main():
    print("=" * 60)
    print("🔐 Zylin AI - Password Generator")
    print("=" * 60)
    print()
    
    passwords = {}
    
    # Generate passwords for all services
    print("📝 Generating secure passwords...\n")
    
    # Database
    passwords['DB_PASSWORD'] = generate_password(32, special_chars=False)
    print(f"✅ PostgreSQL Password: {passwords['DB_PASSWORD'][:8]}...{passwords['DB_PASSWORD'][-4:]}")
    
    # Redis
    passwords['REDIS_PASSWORD'] = generate_password(32, special_chars=False)
    print(f"✅ Redis Password: {passwords['REDIS_PASSWORD'][:8]}...{passwords['REDIS_PASSWORD'][-4:]}")
    
    # Grafana
    passwords['GRAFANA_PASSWORD'] = generate_password(24)
    print(f"✅ Grafana Password: {passwords['GRAFANA_PASSWORD'][:8]}...{passwords['GRAFANA_PASSWORD'][-4:]}")
    
    # JWT Secret
    passwords['JWT_SECRET_KEY'] = generate_password(64, special_chars=False)
    print(f"✅ JWT Secret: {passwords['JWT_SECRET_KEY'][:8]}...{passwords['JWT_SECRET_KEY'][-4:]}")
    
    # API Key Salt
    passwords['API_KEY_SALT'] = secrets.token_hex(32)
    print(f"✅ API Key Salt: {passwords['API_KEY_SALT'][:8]}...{passwords['API_KEY_SALT'][-4:]}")
    
    print()
    print("=" * 60)
    print("📋 Instructions")
    print("=" * 60)
    print()
    print("1. Add these to your .env.production file:")
    print()
    
    for key, value in passwords.items():
        print(f"   {key}={value}")
    
    print()
    print("2. Update Docker Compose and restart services:")
    print("   docker-compose down")
    print("   docker-compose up -d")
    print()
    print("3. For Grafana, login with:")
    print("   URL: http://localhost:3000")
    print("   Username: admin")
    print(f"   Password: {passwords['GRAFANA_PASSWORD']}")
    print()
    print("4. IMPORTANT: Save these passwords in your password manager!")
    print()
    print("=" * 60)
    print("⚠️  Security Reminders")
    print("=" * 60)
    print()
    print("• Never commit passwords to git")
    print("• Store in password manager (1Password, LastPass, etc.)")
    print("• Rotate passwords every 90 days")
    print("• Use different passwords for each service")
    print("• Enable 2FA where available")
    print()
    
    # Save to file (optional)
    save = input("💾 Save passwords to secure file? (yes/no): ").strip().lower()
    
    if save == 'yes':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"passwords_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("Zylin AI - Generated Passwords\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")
            
            for key, value in passwords.items():
                f.write(f"{key}={value}\n")
            
            f.write("\n" + "=" * 60 + "\n")
            f.write("SECURITY WARNING\n")
            f.write("=" * 60 + "\n")
            f.write("• Delete this file after copying passwords to secure storage\n")
            f.write("• Never commit this file to git\n")
            f.write("• Store in password manager\n")
        
        # Secure file permissions (Unix-like systems)
        try:
            os.chmod(filename, 0o600)
        except:
            pass
        
        print(f"\n✅ Passwords saved to: {filename}")
        print("⚠️  Remember to DELETE this file after copying to password manager!")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
