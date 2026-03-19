# Agent A3: KeyManager Encryption Implementation

**Spec**: 007 (Storage Architecture) | **Wave**: 2 (parallel with A2) | **subagent_type**: security-engineer | **Model**: Sonnet 4.6

## Mission

Implement the KeyManager class for Fernet symmetric encryption of API keys. This is the security layer protecting provider credentials stored in SQLite. Keys are encrypted before storage and decrypted only in memory at request time.

## Assigned Tasks

T046-T057 from `specs/007-storage-architecture/tasks.md`:

- T046: `KeyManager.__init__()` loading `EMBEDINATOR_FERNET_KEY` from environment
- T047: `encrypt()` using Fernet AES-128-CBC + HMAC-SHA256
- T048: `decrypt()` with InvalidToken on tampering
- T049: `is_valid_key()` for quick ciphertext validation
- T050: Error handling (ValueError, InvalidToken)
- T051: Security validations (no plaintext logging, no caching, fail-secure)
- T052-T056: Unit tests (encryption, decryption, validation, security)
- T057: Run external test runner

## Critical Constraints

1. **Read the KeyManager contract FIRST**: `specs/007-storage-architecture/contracts/key-manager-contract.md`
2. **NEVER run pytest inside Claude Code**. Use: `zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py`
3. **Environment variable is `EMBEDINATOR_FERNET_KEY`** -- this is mandated by Constitution Principle V. NOT `SECRET_KEY`, NOT `api_key_encryption_secret`.
4. **Load from `os.environ`**, NOT from the Settings class in `config.py`. The `api_key_encryption_secret` field in config.py is a Phase 1 artifact and is NOT used by KeyManager.
5. **NEVER log plaintext keys** -- not in error messages, not in debug logs, nowhere
6. **NEVER cache decrypted keys** -- decrypt fresh each time
7. **Fail-secure**: Missing `EMBEDINATOR_FERNET_KEY` raises ValueError (no silent fallback in production)
8. **Use `monkeypatch.setenv()`** in tests for env var isolation (never `os.environ[]` directly)
9. **Do NOT create integration tests** -- those belong to A4 (Wave 3)
10. **Do NOT modify any other files** -- you own ONLY `key_manager.py` and `test_key_manager.py`

## Deliverables

### 1. backend/providers/key_manager.py

```python
import os
from cryptography.fernet import Fernet, InvalidToken

class KeyManager:
    """Fernet symmetric encryption for API keys.

    Loads EMBEDINATOR_FERNET_KEY from environment. Encrypts API keys
    before storage in SQLite and decrypts only in-memory at request time.
    """

    def __init__(self):
        """Load encryption key from EMBEDINATOR_FERNET_KEY env var.

        Raises:
            ValueError: If EMBEDINATOR_FERNET_KEY is not set.
        """

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext API key.

        Args:
            plaintext: The API key to encrypt.

        Returns:
            Base64-encoded Fernet ciphertext.
        """

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext to plaintext API key.

        Args:
            ciphertext: Fernet-encrypted string from database.

        Returns:
            Plaintext API key (in-memory only).

        Raises:
            ValueError: If ciphertext format is invalid.
            InvalidToken: If HMAC verification fails (tampering detected).
        """

    def is_valid_key(self, ciphertext: str) -> bool:
        """Quick validation without decryption.

        Returns True if ciphertext is a valid Fernet token format.
        Does NOT decrypt -- faster, no exception handling needed.
        """
```

**Key derivation**:
- Read `EMBEDINATOR_FERNET_KEY` from `os.environ`
- This should be a valid Fernet key (base64-encoded 32 bytes)
- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

**Security properties**:
- Fernet provides AES-128-CBC + HMAC-SHA256 (authenticated encryption)
- Ciphertext includes creation timestamp
- HMAC detects any tampering of the ciphertext
- Plaintext is NEVER stored, logged, or cached

### 2. tests/unit/test_key_manager.py

Comprehensive unit tests:

**Initialization**:
- `test_init_with_env_var` -- valid EMBEDINATOR_FERNET_KEY set
- `test_init_missing_env_var` -- raises ValueError

**Encryption**:
- `test_encrypt_plaintext` -- returns base64 ciphertext (not plaintext)
- `test_encrypt_different_plaintexts` -- different inputs produce different ciphertexts
- `test_encrypt_empty_string` -- handles edge case
- `test_encrypt_long_key` -- large API keys work

**Decryption**:
- `test_decrypt_round_trip` -- plaintext -> encrypt -> decrypt -> same plaintext
- `test_decrypt_invalid_format` -- raises ValueError
- `test_decrypt_tampered_ciphertext` -- raises InvalidToken
- `test_decrypt_wrong_key` -- different EMBEDINATOR_FERNET_KEY raises InvalidToken

**Key validation**:
- `test_is_valid_key_true` -- valid ciphertext returns True
- `test_is_valid_key_false` -- corrupted data returns False
- `test_is_valid_key_fast` -- no decryption overhead

**Security** (these are important):
- `test_plaintext_not_logged` -- mock structlog, verify no plaintext in log calls
- `test_no_key_caching` -- decrypted value not stored in instance
- `test_hmac_tampering_detected` -- modify ciphertext bytes, verify InvalidToken
- `test_env_var_isolation` -- different test runs use different keys via monkeypatch

**All tests use `monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", ...)` for isolation.**

## Acceptance Criteria

- KeyManager reads `EMBEDINATOR_FERNET_KEY` from `os.environ` (NOT config.py)
- Encrypt/decrypt round-trip: plaintext -> ciphertext -> plaintext
- Tampered ciphertext raises InvalidToken
- Missing env var raises ValueError (fail-secure)
- `is_valid_key()` returns True/False without decryption
- No plaintext in logs (verified by test)
- No caching of decrypted keys
- All unit tests passing via external runner
- `ruff check backend/providers/key_manager.py` passes

## Testing Protocol

```bash
zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py
cat Docs/Tests/spec07-wave2-keymanager.status
cat Docs/Tests/spec07-wave2-keymanager.summary
```

## Key References

- KeyManager Contract: `specs/007-storage-architecture/contracts/key-manager-contract.md`
- Spec (FR-013): `specs/007-storage-architecture/spec.md`
- Constitution Principle V: `EMBEDINATOR_FERNET_KEY` env var name

## Execution Flow

1. Wait for A1 gate (Wave 1 tests must pass)
2. Read this instruction file
3. Read `specs/007-storage-architecture/contracts/key-manager-contract.md`
4. Create `backend/providers/key_manager.py`
5. Create `tests/unit/test_key_manager.py`
6. Run external test runner
7. Fix failures iteratively
8. Run `ruff check backend/providers/key_manager.py`
9. Signal completion (orchestrator waits for both A2 + A3)

**Wave 2 Gate**: Both A2 and A3 tests must pass before Wave 3 (A4) begins.
