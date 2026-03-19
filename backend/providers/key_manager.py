import base64
import os

from cryptography.fernet import Fernet


class KeyManager:
    """Fernet symmetric encryption for API keys.

    Loads EMBEDINATOR_FERNET_KEY from environment. Encrypts API keys
    before storage in SQLite and decrypts only in-memory at request time.
    """

    def __init__(self) -> None:
        """Load encryption key from EMBEDINATOR_FERNET_KEY env var.

        Raises:
            ValueError: If EMBEDINATOR_FERNET_KEY is not set.
        """
        raw_key = os.environ.get("EMBEDINATOR_FERNET_KEY")
        if not raw_key:
            raise ValueError(
                "EMBEDINATOR_FERNET_KEY environment variable is not set. "
                "Generate with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext API key.

        Args:
            plaintext: The API key to encrypt.

        Returns:
            Base64-encoded Fernet ciphertext.
        """
        return self._fernet.encrypt(plaintext.encode()).decode()

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
        # Pre-validate format: must be valid base64url with Fernet version byte (0x80)
        try:
            data = base64.urlsafe_b64decode(ciphertext + "==")
        except Exception as exc:
            raise ValueError("Invalid ciphertext format: not valid base64") from exc

        if len(data) < 57 or data[0] != 0x80:
            raise ValueError("Invalid ciphertext format: not a Fernet token")

        # Fernet raises InvalidToken if HMAC verification fails (tampering)
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def is_valid_key(self, ciphertext: str) -> bool:
        """Quick validation without decryption.

        Returns True if ciphertext is a valid Fernet token format.
        Does NOT decrypt -- faster, no exception handling needed by caller.
        """
        try:
            data = base64.urlsafe_b64decode(ciphertext + "==")
            return len(data) >= 57 and data[0] == 0x80
        except Exception:
            return False
