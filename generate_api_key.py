"""
Generate Customer API Key
Creates a new customer with an API key for the Zylin platform.
Run this script after deploying to create your first customer account.
"""
import sys
import secrets
from pathlib import Path

# Add parent directory to path to import auth module
sys.path.insert(0, str(Path(__file__).parent))

from backend.auth import hash_api_key
from backend.models import DatabaseManager, create_customer
import structlog

logger = structlog.get_logger(__name__)


def generate_customer(
    customer_name: str,
    email: str,
    plan_type: str = "pro",
    max_calls_per_month: int = 1000,
    max_minutes_per_call: int = 30
):
    """
    Generate a new customer with API key.
    
    Args:
        customer_name: Customer company name
        email: Customer email address
        plan_type: Plan type (free, starter, pro, enterprise)
        max_calls_per_month: Maximum calls allowed per month
        max_minutes_per_call: Maximum minutes per call
    
    Returns:
        Tuple of (customer, api_key) where api_key is the plaintext key to give to customer
    """
    # Generate a secure random API key (32 bytes = 256 bits)
    api_key = secrets.token_urlsafe(32)
    
    # Hash it for storage
    api_key_hash = hash_api_key(api_key)
    
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    session = db_manager.get_session()
    
    try:
        # Create customer record
        customer = create_customer(
            session=session,
            customer_name=customer_name,
            email=email,
            api_key_hash=api_key_hash,
            plan_type=plan_type,
            max_calls_per_month=max_calls_per_month,
            max_minutes_per_call=max_minutes_per_call
        )
        
        logger.info(
            "customer_created",
            customer_id=str(customer.customer_id),
            customer_name=customer_name,
            email=email,
            plan_type=plan_type
        )
        
        return customer, api_key
    
    finally:
        session.close()
        db_manager.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Zylin Customer API Key Generator")
    print("=" * 60)
    print()
    
    # Interactive prompts
    customer_name = input("Customer Name: ").strip()
    email = input("Email: ").strip()
    
    print("\nPlan Types:")
    print("  1. free     - 100 calls/month, 10 min/call")
    print("  2. starter  - 500 calls/month, 20 min/call")
    print("  3. pro      - 1000 calls/month, 30 min/call")
    print("  4. enterprise - 10000 calls/month, 60 min/call")
    print("  5. custom   - Specify custom limits")
    
    plan_choice = input("\nSelect plan (1-5): ").strip()
    
    plan_configs = {
        "1": ("free", 100, 10),
        "2": ("starter", 500, 20),
        "3": ("pro", 1000, 30),
        "4": ("enterprise", 10000, 60),
    }
    
    if plan_choice in plan_configs:
        plan_type, max_calls, max_minutes = plan_configs[plan_choice]
    elif plan_choice == "5":
        plan_type = input("Plan type name: ").strip()
        max_calls = int(input("Max calls per month: ").strip())
        max_minutes = int(input("Max minutes per call: ").strip())
    else:
        print("Invalid choice. Using 'pro' plan.")
        plan_type, max_calls, max_minutes = "pro", 1000, 30
    
    print("\n" + "=" * 60)
    print("Creating customer...")
    print("=" * 60)
    
    try:
        customer, api_key = generate_customer(
            customer_name=customer_name,
            email=email,
            plan_type=plan_type,
            max_calls_per_month=max_calls,
            max_minutes_per_call=max_minutes
        )
        
        print("\n✅ Customer created successfully!\n")
        print("=" * 60)
        print("CUSTOMER DETAILS")
        print("=" * 60)
        print(f"Customer ID:    {customer.customer_id}")
        print(f"Name:           {customer.customer_name}")
        print(f"Email:          {customer.email}")
        print(f"Plan:           {customer.plan_type}")
        print(f"Max Calls:      {customer.max_calls_per_month}/month")
        print(f"Max Minutes:    {customer.max_minutes_per_call} min/call")
        print()
        print("=" * 60)
        print("⚠️  API KEY - SAVE THIS SECURELY!")
        print("=" * 60)
        print(f"{api_key}")
        print()
        print("⚠️  This key will NOT be shown again!")
        print("   Give this key to the customer for authentication.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error creating customer: {e}")
        sys.exit(1)
