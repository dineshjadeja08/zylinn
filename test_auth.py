"""
Test Authentication System
Tests signup, login, verification, and password reset flows.
"""
import requests
import time

# Configuration
API_URL = "http://localhost:8000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPass123"
TEST_NAME = "Test User"
TEST_COMPANY = "Test Company"


def test_signup():
    """Test user signup"""
    print("\n" + "="*60)
    print("TEST 1: User Signup")
    print("="*60)
    
    response = requests.post(
        f"{API_URL}/auth/signup",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
            "company_name": TEST_COMPANY
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200, "Signup failed"
    assert "check your email" in response.json()["message"].lower()
    print("✅ Signup successful!")


def test_login_unverified():
    """Test login before email verification"""
    print("\n" + "="*60)
    print("TEST 2: Login (Unverified)")
    print("="*60)
    
    response = requests.post(
        f"{API_URL}/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 403, "Should reject unverified users"
    assert "verify" in response.json()["detail"].lower()
    print("✅ Correctly rejects unverified user!")


def test_login_wrong_password():
    """Test login with wrong password"""
    print("\n" + "="*60)
    print("TEST 3: Login (Wrong Password)")
    print("="*60)
    
    response = requests.post(
        f"{API_URL}/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 401, "Should reject wrong password"
    print("✅ Correctly rejects wrong password!")


def test_forgot_password():
    """Test forgot password flow"""
    print("\n" + "="*60)
    print("TEST 4: Forgot Password")
    print("="*60)
    
    response = requests.post(
        f"{API_URL}/auth/forgot-password",
        json={
            "email": TEST_EMAIL
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200, "Forgot password failed"
    print("✅ Password reset email sent!")


def test_api_health():
    """Test API health endpoint"""
    print("\n" + "="*60)
    print("TEST 0: API Health Check")
    print("="*60)
    
    response = requests.get(f"{API_URL}/health")
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200, "API not healthy"
    print("✅ API is healthy!")


if __name__ == "__main__":
    print("\n" + "🧪 " + "="*58)
    print("   AUTHENTICATION SYSTEM TEST SUITE")
    print("="*60)
    print(f"API URL: {API_URL}")
    print(f"Test Email: {TEST_EMAIL}")
    print("="*60)
    
    try:
        # Test API health
        test_api_health()
        
        # Test signup
        test_signup()
        
        # Wait a moment
        time.sleep(1)
        
        # Test login unverified
        test_login_unverified()
        
        # Test wrong password
        test_login_wrong_password()
        
        # Test forgot password
        test_forgot_password()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n📧 Next steps:")
        print("1. Check email for verification link")
        print("2. Click verification link")
        print("3. Check email for API key")
        print("4. Try login again")
        print("\n💡 To test verified login:")
        print(f"   1. Get verification token from database")
        print(f"   2. Visit: {API_URL}/auth/verify-email/{{token}}")
        print(f"   3. Then test login again")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {API_URL}")
        print("   Make sure the backend is running:")
        print("   cd backend && python app.py")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        exit(1)
