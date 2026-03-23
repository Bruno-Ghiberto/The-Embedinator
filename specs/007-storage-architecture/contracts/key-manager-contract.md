# KeyManager Encryption Contract

**Feature**: Storage Architecture | **Date**: 2026-03-13 | **Version**: 1.0

## Overview

Internal contract defining the KeyManager class interface for API key encryption/decryption. This is the security layer protecting sensitive provider credentials stored in SQLite.

## Class: KeyManager

**Module**: `backend.providers.key_manager`

**Responsibility**: Symmetric encryption/decryption of API keys using Fernet cipher, key derivation from environment, secure in-memory handling.

### Public Methods

#### Initialization

```python
class KeyManager:
    def __init__(self)
```

**Contract**:
- Loads encryption key from environment variable (e.g., EMBEDINATOR_FERNET_KEY)
- Derives Fernet key from provided secret (or generates random if not present)
- Key stored in memory, never logged or written to disk except in env

---

#### Encryption

```python
def encrypt(plaintext: str) -> str
```

**Contract**:
- Takes plaintext API key (e.g., "sk-proj-abc123...")
- Returns Fernet ciphertext (base64-encoded)
- Raises: ValueError if key not initialized

**Security Properties**:
- Deterministic encryption: Same plaintext + key → same ciphertext (safe for upsert)
- Authentication: Fernet includes HMAC verification
- Timestamp-protected: Ciphertext includes creation timestamp, can detect old keys

**Example**:
```python
plaintext_key = "sk-proj-1234567890abcdef"
ciphertext = km.encrypt(plaintext_key)
# Result: "gAAAAABlZ7h5..."  (base64-encoded, ~88 chars)
```

---

#### Decryption

```python
def decrypt(ciphertext: str) -> str
```

**Contract**:
- Takes Fernet ciphertext (from database)
- Returns plaintext API key
- Raises:
  - ValueError: If ciphertext is invalid (corrupted, wrong key, expired)
  - InvalidToken: If HMAC verification fails (tampering detected)

**Security Properties**:
- Decrypted only in-memory (never stored, never logged)
- Failure raises exception (no silent fallback)
- Used only at request time (not cached)

**Example**:
```python
plaintext_key = km.decrypt(ciphertext)
# Use plaintext_key for API request
# Key cleared from memory when function scope ends (Python GC)
```

---

#### Key Validation

```python
def is_valid_key(ciphertext: str) -> bool
```

**Contract**:
- Quick validation without decryption
- Checks Fernet token format and signature
- Returns True if valid, False if corrupted/invalid
- Does NOT decrypt (faster, no exception handling needed)

**Use Case**:
- Database migration: Validate all stored keys without decrypting all

---

## Error Handling

### Expected Exceptions

| Exception | Scenario | Recovery |
|-----------|----------|----------|
| ValueError | Key not initialized (env var missing) | Startup fails, admin must set EMBEDINATOR_FERNET_KEY |
| ValueError | Invalid ciphertext format | Log error, return error to user (provider disabled) |
| InvalidToken | HMAC verification failed | Log security warning (possible tampering), disable provider |
| cryptography.InvalidSignature | Ciphertext tampered | Treat as security incident, disable provider |

### Error Messages

- Avoid exposing ciphertext in error logs
- Log only: "Failed to decrypt provider key for 'openai'" (not the key itself)
- Return to user: "Provider configuration error" (generic message)

---

## Key Management

### Key Derivation

```
Secret: EMBEDINATOR_FERNET_KEY (32+ bytes, base64-encoded)
Fernet Key: base64(Fernet(secret))
```

**Contract**:
- Environment variable: EMBEDINATOR_FERNET_KEY
- Format: Base64-encoded 32-byte secret (generated with `os.urandom(32)`)
- Example setup:
  ```bash
  python -c "import os; print(base64.b64encode(os.urandom(32)).decode())"
  # Output: "xK7pQ9mN2LZ8fV3jX1aB0cD4eF6gH9iJ..."
  export EMBEDINATOR_FERNET_KEY="xK7pQ9mN2LZ8fV3jX1aB0cD4eF6gH9iJ..."
  ```

### Key Rotation

**Not in Scope**: Initial feature supports single key. Future rotation would require:
1. Decrypt all keys with old key
2. Re-encrypt with new key
3. Update EMBEDINATOR_FERNET_KEY env var
4. Restart services

### Key Storage

- **Allowed**: Environment variables (secure, not in code)
- **Allowed**: Secret management systems (Vault, AWS Secrets Manager) via env var
- **NOT Allowed**: Plaintext in .env files (git-ignored but risky), hardcoded in code, logs

---

## Usage Examples

### Encryption at Provider Creation

```python
from backend.providers.key_manager import KeyManager

km = KeyManager()

# User provides API key
plaintext_key = "sk-proj-1234567890abcdef"

# Encrypt before storing
ciphertext = km.encrypt(plaintext_key)

# Store ciphertext in database
await db.create_provider(
    name="openai",
    api_key_encrypted=ciphertext,
    base_url=None,
    is_active=True
)
```

### Decryption at Request Time

```python
from backend.providers.key_manager import KeyManager

km = KeyManager()

# Retrieve ciphertext from database
provider = await db.get_provider("openai")
ciphertext = provider["api_key_encrypted"]

# Decrypt in-memory (only at request time)
plaintext_key = km.decrypt(ciphertext)

# Use plaintext_key for API request
response = await openai_client.call(api_key=plaintext_key, ...)

# plaintext_key cleared from memory when scope ends
```

### Key Validation During Migration

```python
from backend.providers.key_manager import KeyManager

km = KeyManager()

# Check all stored keys without decrypting
providers = await db.list_providers()
for provider in providers:
    if provider["api_key_encrypted"]:
        is_valid = km.is_valid_key(provider["api_key_encrypted"])
        print(f"Provider {provider['name']}: {'valid' if is_valid else 'corrupted'}")
```

---

## Security Properties

### Confidentiality

- API keys stored as ciphertext in SQLite (no plaintext at rest)
- Decryption happens only in-memory (volatile, cleared by GC)
- Secret key isolated in environment (not in code, not in logs)

### Integrity

- Fernet HMAC authenticates ciphertext (tampering detected)
- InvalidToken exception on verification failure
- No silent corruption possible

### Availability

- Missing EMBEDINATOR_FERNET_KEY → startup fails (fail-secure)
- Corrupted ciphertext → provider disabled (manual recovery)
- Key rotation requires restart (operational burden)

### Non-Repudiation

- Each encryption includes timestamp (can detect old keys)
- Logs include provider name + operation, not keys
- Audit trail via query_traces (user queries) and logs (system events)

---

## Dependencies

### External Libraries

- **cryptography >=44.0**: Fernet symmetric encryption
  - Used: `cryptography.fernet.Fernet`
  - Provides: AES128-CBC with HMAC-SHA256

### Internal Dependencies

- None (pure encryption utility, no business logic)

---

## Testing Considerations

### Unit Tests

- Encrypt/decrypt round-trip: plaintext → encrypt → decrypt → plaintext ✓
- Invalid ciphertext: Raises InvalidToken or ValueError ✓
- Missing key (env var): Raises ValueError ✓
- Key validation: is_valid_key returns True/False correctly ✓

### Integration Tests

- Provider creation with encrypted key (create_provider + encrypt)
- Provider retrieval with decryption (get_provider + decrypt)
- Key rotation scenario: Multiple providers with same/different keys

### Security Tests

- Ensure plaintext never logged (mock logger)
- Verify no key caching (fresh decrypt per call)
- Confirm HMAC failure on tampered ciphertext

---

## Performance Characteristics

| Operation | Target | Notes |
|-----------|--------|-------|
| encrypt(key) | <1ms | Fernet overhead minimal |
| decrypt(ciphertext) | <1ms | Fernet with HMAC |
| is_valid_key(ciphertext) | <0.5ms | Quick format check |
| __init__() | <10ms | Key derivation from env |

---

## Configuration

### Environment Variables

```bash
# Required for encryption
export EMBEDINATOR_FERNET_KEY="base64-encoded-32-byte-secret"

# Optional: Control Fernet token TTL (future feature)
# export EMBEDINATOR_KEY_TTL_SECONDS=86400
```

### No Configuration in Code

All encryption parameters fixed by Fernet standard:
- Cipher: AES128-CBC
- HMAC: SHA256
- Padding: PKCS7 (automatic)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Initial contract definition for KeyManager |
