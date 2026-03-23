"""Unit tests for KeyManager Fernet encryption.

Tests cover initialization, encrypt/decrypt round-trip, key validation,
and security properties (no plaintext logging, no caching).
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from backend.providers.key_manager import KeyManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def key_manager(monkeypatch, fernet_key) -> KeyManager:
    monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", fernet_key)
    return KeyManager()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_with_env_var(self, monkeypatch, fernet_key):
        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", fernet_key)
        km = KeyManager()
        assert km._fernet is not None

    def test_init_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("EMBEDINATOR_FERNET_KEY", raising=False)
        with pytest.raises(ValueError, match="EMBEDINATOR_FERNET_KEY"):
            KeyManager()

    def test_init_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", "")
        with pytest.raises(ValueError, match="EMBEDINATOR_FERNET_KEY"):
            KeyManager()


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

class TestEncrypt:
    def test_encrypt_plaintext(self, key_manager):
        ciphertext = key_manager.encrypt("sk-proj-abc123")
        assert isinstance(ciphertext, str)
        assert ciphertext != "sk-proj-abc123"

    def test_encrypt_returns_base64(self, key_manager):
        ciphertext = key_manager.encrypt("sk-test-key")
        # Must be valid base64url
        decoded = base64.urlsafe_b64decode(ciphertext + "==")
        assert len(decoded) > 0

    def test_encrypt_different_plaintexts(self, key_manager):
        ct1 = key_manager.encrypt("sk-key-one")
        ct2 = key_manager.encrypt("sk-key-two")
        assert ct1 != ct2

    def test_encrypt_same_plaintext_produces_different_ciphertexts(self, key_manager):
        # Fernet uses random IV so same plaintext → different ciphertext each call
        plaintext = "sk-same-key"
        ct1 = key_manager.encrypt(plaintext)
        ct2 = key_manager.encrypt(plaintext)
        assert ct1 != ct2

    def test_encrypt_empty_string(self, key_manager):
        ciphertext = key_manager.encrypt("")
        assert isinstance(ciphertext, str)
        assert len(ciphertext) > 0

    def test_encrypt_long_key(self, key_manager):
        long_key = "sk-" + "x" * 512
        ciphertext = key_manager.encrypt(long_key)
        assert isinstance(ciphertext, str)
        assert len(ciphertext) > len(long_key)


# ---------------------------------------------------------------------------
# Decryption
# ---------------------------------------------------------------------------

class TestDecrypt:
    def test_decrypt_round_trip(self, key_manager):
        plaintext = "sk-proj-round-trip-1234567890"
        ciphertext = key_manager.encrypt(plaintext)
        result = key_manager.decrypt(ciphertext)
        assert result == plaintext

    def test_decrypt_empty_string(self, key_manager):
        ciphertext = key_manager.encrypt("")
        assert key_manager.decrypt(ciphertext) == ""

    def test_decrypt_long_key(self, key_manager):
        plaintext = "sk-" + "a" * 512
        ciphertext = key_manager.encrypt(plaintext)
        assert key_manager.decrypt(ciphertext) == plaintext

    def test_decrypt_invalid_format(self, key_manager):
        with pytest.raises(ValueError):
            key_manager.decrypt("not-a-valid-token!!!")

    def test_decrypt_invalid_format_plain_text(self, key_manager):
        with pytest.raises(ValueError):
            key_manager.decrypt("plaintext-api-key")

    def test_decrypt_invalid_format_empty(self, key_manager):
        with pytest.raises(ValueError):
            key_manager.decrypt("")

    def test_decrypt_tampered_ciphertext(self, key_manager):
        ciphertext = key_manager.encrypt("sk-original-key")
        # Flip bytes in the middle of the base64 ciphertext to corrupt HMAC
        chars = list(ciphertext)
        mid = len(chars) // 2
        chars[mid] = "A" if chars[mid] != "A" else "B"
        tampered = "".join(chars)
        with pytest.raises((InvalidToken, ValueError)):
            key_manager.decrypt(tampered)

    def test_decrypt_wrong_key(self, monkeypatch):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key1)
        km1 = KeyManager()
        ciphertext = km1.encrypt("sk-super-secret")

        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key2)
        km2 = KeyManager()
        with pytest.raises((InvalidToken, ValueError)):
            km2.decrypt(ciphertext)


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

class TestIsValidKey:
    def test_is_valid_key_true(self, key_manager):
        ciphertext = key_manager.encrypt("sk-valid-key")
        assert key_manager.is_valid_key(ciphertext) is True

    def test_is_valid_key_false_corrupted(self, key_manager):
        assert key_manager.is_valid_key("corrupted-data") is False

    def test_is_valid_key_false_empty(self, key_manager):
        assert key_manager.is_valid_key("") is False

    def test_is_valid_key_false_random_bytes(self, key_manager):
        # Random base64 that doesn't start with Fernet version byte
        garbage = base64.urlsafe_b64encode(b"\x00" * 80).decode()
        assert key_manager.is_valid_key(garbage) is False

    def test_is_valid_key_false_plain_text(self, key_manager):
        assert key_manager.is_valid_key("sk-plaintext-key-1234") is False

    def test_is_valid_key_fast(self, key_manager, monkeypatch):
        """is_valid_key must not call Fernet.decrypt internally."""
        decrypt_calls = []
        original_decrypt = key_manager._fernet.decrypt

        def tracking_decrypt(*args, **kwargs):
            decrypt_calls.append(True)
            return original_decrypt(*args, **kwargs)

        monkeypatch.setattr(key_manager._fernet, "decrypt", tracking_decrypt)

        ciphertext = key_manager.encrypt("sk-fast-check")
        result = key_manager.is_valid_key(ciphertext)

        assert result is True
        assert len(decrypt_calls) == 0  # decrypt was NOT called


# ---------------------------------------------------------------------------
# Security properties
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_plaintext_not_logged(self, key_manager):
        """Plaintext API key must never appear in structlog output."""
        plaintext = "sk-ultra-secret-key-do-not-log"
        log_calls = []

        mock_logger = MagicMock()
        mock_logger.side_effect = lambda *a, **kw: log_calls.append((a, kw))

        with patch("structlog.get_logger", return_value=mock_logger):
            ciphertext = key_manager.encrypt(plaintext)
            key_manager.decrypt(ciphertext)

        for args, kwargs in log_calls:
            assert plaintext not in str(args), "Plaintext found in log args"
            assert plaintext not in str(kwargs), "Plaintext found in log kwargs"

    def test_no_key_caching(self, monkeypatch, fernet_key):
        """Decrypted plaintext must not be stored as an instance attribute."""
        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", fernet_key)
        km = KeyManager()
        plaintext = "sk-must-not-be-cached"
        ciphertext = km.encrypt(plaintext)

        _ = km.decrypt(ciphertext)

        # Plaintext must not appear anywhere in instance state
        instance_state = str(vars(km))
        assert plaintext not in instance_state

    def test_hmac_tampering_detected(self, key_manager):
        """Modifying ciphertext bytes must raise InvalidToken (HMAC failure)."""
        ciphertext = key_manager.encrypt("sk-original-value")
        raw = base64.urlsafe_b64decode(ciphertext + "==")

        # Flip a bit in the HMAC section (last 32 bytes)
        tampered_raw = bytearray(raw)
        tampered_raw[-1] ^= 0xFF
        tampered = base64.urlsafe_b64encode(bytes(tampered_raw)).decode().rstrip("=")

        with pytest.raises((InvalidToken, ValueError)):
            key_manager.decrypt(tampered)

    def test_env_var_isolation(self, monkeypatch):
        """Each test can set its own EMBEDINATOR_FERNET_KEY independently."""
        key_a = Fernet.generate_key().decode()
        key_b = Fernet.generate_key().decode()

        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key_a)
        km_a = KeyManager()
        ct = km_a.encrypt("sk-isolated-key")

        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key_b)
        km_b = KeyManager()

        # Different key → cannot decrypt
        with pytest.raises((InvalidToken, ValueError)):
            km_b.decrypt(ct)

    def test_fernet_key_not_logged(self, monkeypatch, fernet_key):
        """The Fernet key itself must not appear in any log output."""
        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", fernet_key)
        log_calls = []

        mock_logger = MagicMock()
        mock_logger.side_effect = lambda *a, **kw: log_calls.append((a, kw))

        with patch("structlog.get_logger", return_value=mock_logger):
            km = KeyManager()
            km.encrypt("sk-test")

        for args, kwargs in log_calls:
            assert fernet_key not in str(args), "Fernet key found in log args"
            assert fernet_key not in str(kwargs), "Fernet key found in log kwargs"
