"""
Chat Crypto Module - End-to-end encryption for team chat

Uses NaCl (libsodium) for asymmetric encryption:
- Each user has a keypair (private in ~/.set-core/chat-keys/, public in member.json)
- Messages are encrypted with nacl.public.Box for sender-recipient pairs
- The Box automatically derives a shared key from the keypairs
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import base64

try:
    from nacl.public import PrivateKey, PublicKey, Box
    from nacl.encoding import Base64Encoder
    from nacl.utils import random
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


# Key storage directory
KEYS_DIR = Path.home() / ".set-core" / "chat-keys"


def is_available() -> bool:
    """Check if NaCl crypto is available"""
    return NACL_AVAILABLE


def get_project_key_path(project_name: str) -> Path:
    """Get path to private key file for a project"""
    return KEYS_DIR / f"{project_name}.key"


def generate_keypair(project_name: str, force: bool = False) -> Tuple[str, str]:
    """
    Generate a new keypair for a project.

    Returns:
        Tuple of (public_key_base64, fingerprint)

    Raises:
        RuntimeError: If key already exists and force=False
        ImportError: If NaCl is not available
    """
    if not NACL_AVAILABLE:
        raise ImportError("PyNaCl is not installed. Run: pip install PyNaCl")

    key_path = get_project_key_path(project_name)

    if key_path.exists() and not force:
        raise RuntimeError(f"Key already exists at {key_path}. Use force=True to regenerate.")

    # Ensure directory exists
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # Set restrictive permissions on directory
    os.chmod(KEYS_DIR, 0o700)

    # Generate new keypair
    private_key = PrivateKey.generate()
    public_key = private_key.public_key

    # Save private key (base64 encoded)
    private_b64 = base64.b64encode(bytes(private_key)).decode('ascii')
    with open(key_path, 'w') as f:
        f.write(private_b64)

    # Set restrictive permissions on key file
    os.chmod(key_path, 0o600)

    # Return public key and fingerprint
    public_b64 = base64.b64encode(bytes(public_key)).decode('ascii')
    fingerprint = compute_fingerprint(public_b64)

    return public_b64, fingerprint


def load_private_key(project_name: str) -> Optional['PrivateKey']:
    """Load private key for a project"""
    if not NACL_AVAILABLE:
        return None

    key_path = get_project_key_path(project_name)
    if not key_path.exists():
        return None

    with open(key_path, 'r') as f:
        private_b64 = f.read().strip()

    private_bytes = base64.b64decode(private_b64)
    return PrivateKey(private_bytes)


def load_public_key(public_key_b64: str) -> Optional['PublicKey']:
    """Load public key from base64 string"""
    if not NACL_AVAILABLE:
        return None

    try:
        public_bytes = base64.b64decode(public_key_b64)
        return PublicKey(public_bytes)
    except Exception:
        return None


def get_public_key(project_name: str) -> Optional[Tuple[str, str]]:
    """
    Get public key and fingerprint for a project.

    Returns:
        Tuple of (public_key_base64, fingerprint) or None if no key exists
    """
    if not NACL_AVAILABLE:
        return None

    private_key = load_private_key(project_name)
    if private_key is None:
        return None

    public_key = private_key.public_key
    public_b64 = base64.b64encode(bytes(public_key)).decode('ascii')
    fingerprint = compute_fingerprint(public_b64)

    return public_b64, fingerprint


def compute_fingerprint(public_key_b64: str) -> str:
    """Compute a short fingerprint for a public key"""
    # SHA256 hash, take first 8 hex chars
    hash_bytes = hashlib.sha256(public_key_b64.encode()).digest()
    return hash_bytes[:4].hex()


def has_key(project_name: str) -> bool:
    """Check if a key exists for a project"""
    return get_project_key_path(project_name).exists()


def encrypt_message(
    project_name: str,
    recipient_public_key_b64: str,
    plaintext: str
) -> Optional[Tuple[str, str]]:
    """
    Encrypt a message for a recipient.

    Args:
        project_name: Project name (to get sender's private key)
        recipient_public_key_b64: Recipient's public key (base64)
        plaintext: Message to encrypt

    Returns:
        Tuple of (encrypted_base64, nonce_base64) or None on error
    """
    if not NACL_AVAILABLE:
        return None

    # Load our private key
    private_key = load_private_key(project_name)
    if private_key is None:
        return None

    # Load recipient's public key
    recipient_public = load_public_key(recipient_public_key_b64)
    if recipient_public is None:
        return None

    # Create Box for encryption
    box = Box(private_key, recipient_public)

    # Encrypt with random nonce
    plaintext_bytes = plaintext.encode('utf-8')
    encrypted = box.encrypt(plaintext_bytes)

    # Split nonce and ciphertext
    nonce = encrypted.nonce
    ciphertext = encrypted.ciphertext

    nonce_b64 = base64.b64encode(nonce).decode('ascii')
    ciphertext_b64 = base64.b64encode(ciphertext).decode('ascii')

    return ciphertext_b64, nonce_b64


def decrypt_message(
    project_name: str,
    sender_public_key_b64: str,
    ciphertext_b64: str,
    nonce_b64: str
) -> Optional[str]:
    """
    Decrypt a message from a sender.

    Args:
        project_name: Project name (to get recipient's private key)
        sender_public_key_b64: Sender's public key (base64)
        ciphertext_b64: Encrypted message (base64)
        nonce_b64: Nonce used for encryption (base64)

    Returns:
        Decrypted message string or None on error
    """
    if not NACL_AVAILABLE:
        return None

    # Load our private key
    private_key = load_private_key(project_name)
    if private_key is None:
        return None

    # Load sender's public key
    sender_public = load_public_key(sender_public_key_b64)
    if sender_public is None:
        return None

    try:
        # Decode base64
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)

        # Create Box for decryption
        box = Box(private_key, sender_public)

        # Decrypt
        plaintext_bytes = box.decrypt(ciphertext, nonce)
        return plaintext_bytes.decode('utf-8')
    except Exception:
        return None


class ChatMessage:
    """Represents a chat message"""

    def __init__(
        self,
        id: str,
        timestamp: str,
        from_member: str,
        to_member: str,
        encrypted: str,
        nonce: str,
        plaintext: Optional[str] = None
    ):
        self.id = id
        self.timestamp = timestamp
        self.from_member = from_member
        self.to_member = to_member
        self.encrypted = encrypted
        self.nonce = nonce
        self.plaintext = plaintext  # Decrypted content

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict (excludes plaintext)"""
        return {
            "id": self.id,
            "ts": self.timestamp,
            "from": self.from_member,
            "to": self.to_member,
            "enc": self.encrypted,
            "nonce": self.nonce
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ChatMessage':
        """Create from dict"""
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("ts", ""),
            from_member=data.get("from", ""),
            to_member=data.get("to", ""),
            encrypted=data.get("enc", ""),
            nonce=data.get("nonce", "")
        )

    def to_json_line(self) -> str:
        """Convert to JSONL format (single line)"""
        return json.dumps(self.to_dict())


class ChatReadState:
    """Tracks read state for chat messages"""

    STATE_FILE = Path.home() / ".set-core" / "chat-read-state.json"

    def __init__(self):
        self.last_read_id: dict[str, str] = {}  # {project: last_read_message_id}
        self.last_read_ts: dict[str, str] = {}  # {project: last_read_timestamp}
        self.load()

    def load(self):
        """Load state from file"""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    data = json.load(f)
                    self.last_read_id = data.get("last_read_id", {})
                    self.last_read_ts = data.get("last_read_ts", {})
            except Exception:
                pass

    def save(self):
        """Save state to file"""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.STATE_FILE, 'w') as f:
                json.dump({
                    "last_read_id": self.last_read_id,
                    "last_read_ts": self.last_read_ts
                }, f, indent=2)
        except Exception:
            pass

    def mark_read(self, project: str, message_id: str, timestamp: str):
        """Mark a message as read"""
        self.last_read_id[project] = message_id
        self.last_read_ts[project] = timestamp
        self.save()

    def is_unread(self, project: str, message_id: str, timestamp: str) -> bool:
        """Check if a message is unread"""
        last_ts = self.last_read_ts.get(project)
        if not last_ts:
            return True
        return timestamp > last_ts

    def get_last_read_ts(self, project: str) -> Optional[str]:
        """Get last read timestamp for a project"""
        return self.last_read_ts.get(project)
