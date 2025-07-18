import pytest
from datetime import timedelta, datetime
import time

from karyaksham_api.auth import security
from karyaksham_api.auth import jwt
from karyaksham_api.auth.jwt import AuthJWTError
from karyaksham_api.core.config import settings
from jose import jwt as jose_jwt # For creating tokens with different secrets/payloads for testing

# Test data
TEST_PASSWORD = "testpassword123"
TEST_SUBJECT = "testuser@example.com"
TEST_SECRET_KEY = "super_secret_test_key_for_jwt_unit_tests_1234567890"

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """
    Fixture to mock settings.SECRET_KEY and ALGORITHM for predictable JWT testing.
    This ensures tests don't rely on the .env file or default system settings,
    making them isolated and reproducible.
    """
    monkeypatch.setattr(settings, "SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)

# --- Test cases for security.py (Password Hashing) ---

def test_get_password_hash():
    """
    Test that get_password_hash returns a valid bcrypt hash string.
    """
    hashed_password = security.get_password_hash(TEST_PASSWORD)
    assert isinstance(hashed_password, str)
    assert len(hashed_password) > 0
    assert hashed_password.startswith("$2b$") # bcrypt hash prefix

def test_verify_password_correct():
    """
    Test that verify_password returns True for a correct password against its hash.
    """
    hashed_password = security.get_password_hash(TEST_PASSWORD)
    assert security.verify_password(TEST_PASSWORD, hashed_password) is True

def test_verify_password_incorrect():
    """
    Test that verify_password returns False for an incorrect password against its hash.
    """
    hashed_password = security.get_password_hash(TEST_PASSWORD)
    assert security.verify_password("wrongpassword", hashed_password) is False

def test_verify_password_hash_mismatch():
    """
    Test that verify_password returns False for a hash that doesn't match the format
    or is otherwise invalid.
    """
    # A hash that is not a valid bcrypt hash format
    invalid_hash_format = "$2b$12$notavalidhashformat"
    assert security.verify_password(TEST_PASSWORD, invalid_hash_format) is False

    # A completely random string, not a hash
    random_string = "thisisnotahash"
    assert security.verify_password(TEST_PASSWORD, random_string) is False

# --- Test cases for jwt.py (JWT operations) ---

def test_create_access_token():
    """
    Test that create_access_token generates a non-empty string which is a valid JWT.
    """
    token = jwt.create_access_token(TEST_SUBJECT)
    assert isinstance(token, str)
    assert len(token) > 0
    # Basic check to ensure it has the three segments of a JWT
    assert token.count('.') == 2

def test_verify_token_valid():
    """
    Test that a valid token can be successfully verified and returns the correct subject.
    """
    token = jwt.create_access_token(TEST_SUBJECT)
    verified_subject = jwt.verify_token(token)
    assert verified_subject == TEST_SUBJECT

def test_verify_token_expired():
    """
    Test that an expired token raises AuthJWTError with an appropriate message.
    """
    # Create a token that expired in the past
    expired_token = jwt.create_access_token(TEST_SUBJECT, expires_delta=timedelta(seconds=-1))
    
    # Introduce a tiny delay to ensure the system clock has moved past the expiration time
    # if `datetime.utcnow()` is not perfectly aligned across calls or environments.
    time.sleep(0.01)

    with pytest.raises(AuthJWTError, match="Signature has expired"):
        jwt.verify_token(expired_token)

def test_verify_token_invalid_signature():
    """
    Test that a token created with a different (invalid) secret key raises AuthJWTError.
    """
    # Create a token using a secret key different from the one mocked for tests
    malicious_token = jose_jwt.encode(
        {"sub": TEST_SUBJECT, "exp": datetime.utcnow() + timedelta(minutes=30)},
        "totally_different_and_invalid_secret_key",
        algorithm="HS256"
    )

    with pytest.raises(AuthJWTError, match="Invalid signature"):
        jwt.verify_token(malicious_token)

def test_verify_token_malformed():
    """
    Test that a malformed (non-JWT compliant) token string raises AuthJWTError.
    """
    malformed_token_segments = "this.is.not.a.jwt"
    with pytest.raises(AuthJWTError, match="Not enough segments|Error decoding signature"):
        jwt.verify_token(malformed_token_segments)

    empty_token = ""
    with pytest.raises(AuthJWTError, match="Not enough segments"):
        jwt.verify_token(empty_token)

    # A token with valid segments but non-base64url encoded content
    invalid_base64_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid!.signature"
    with pytest.raises(AuthJWTError, match="Invalid header padding|Invalid payload padding"):
        jwt.verify_token(invalid_base64_token)

def test_verify_token_subject_missing():
    """
    Test that a token missing the 'sub' (subject) claim raises AuthJWTError.
    """
    # Manually create a JWT payload without the 'sub' claim
    token_without_sub = jose_jwt.encode(
        {"exp": datetime.utcnow() + timedelta(minutes=30)},
        TEST_SECRET_KEY,
        algorithm="HS256"
    )

    with pytest.raises(AuthJWTError, match="Subject missing"):
        jwt.verify_token(token_without_sub)

def test_create_access_token_with_custom_expiry():
    """
    Test that create_access_token correctly uses a custom expires_delta
    and the token becomes invalid after that duration.
    """
    custom_delta = timedelta(seconds=1)
    token = jwt.create_access_token(TEST_SUBJECT, expires_delta=custom_delta)
    
    # Verify the token is valid immediately after creation (within its short window)
    verified_subject = jwt.verify_token(token)
    assert verified_subject == TEST_SUBJECT

    # Wait for the token to expire
    time.sleep(custom_delta.total_seconds() + 0.1) # Wait slightly longer than the expiry

    # Test that the token is now expired
    with pytest.raises(AuthJWTError, match="Signature has expired"):
        jwt.verify_token(token)
<ctrl63>