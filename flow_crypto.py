import os
import base64
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key

_private_key_cached = None


def get_private_key():
    """Loads and caches the RSA private key from env var or local file."""
    global _private_key_cached
    if _private_key_cached is not None:
        return _private_key_cached

    # Check env var first (handy for Railway deployments)
    env_key = os.getenv("FLOW_PRIVATE_KEY", "").strip()
    if env_key:
        # Restore newlines if stored on single line
        if "\\n" in env_key:
            env_key = env_key.replace("\\n", "\n")
        _private_key_cached = load_pem_private_key(env_key.encode("utf-8"), password=None)
        return _private_key_cached

    # Fallback to local file
    file_path = os.path.join(os.path.dirname(__file__), "flow_private_key.pem")
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            _private_key_cached = load_pem_private_key(f.read(), password=None)
            return _private_key_cached

    raise ValueError("FLOW_PRIVATE_KEY is not configured in .env and flow_private_key.pem not found.")


def decrypt_flow_request(encrypted_aes_key_b64: str, encrypted_flow_data_b64: str, initial_vector_b64: str):
    """
    Decrypts an incoming WhatsApp Flow request.
    1. Decrypts the 128-bit AES key using RSA-OAEP with SHA-256.
    2. Decrypts the payload using AES-128-GCM.
    Returns: (decrypted_json_dict, aes_key_bytes, iv_bytes)
    """
    private_key = get_private_key()

    encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
    encrypted_flow_data = base64.b64decode(encrypted_flow_data_b64)
    iv = base64.b64decode(initial_vector_b64)

    # 1. Decrypt AES key with RSA-OAEP (SHA-256)
    aes_key = private_key.decrypt(
        encrypted_aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # 2. Extract 128-bit (16 bytes) tag from end of encrypted_flow_data
    ciphertext = encrypted_flow_data[:-16]
    auth_tag = encrypted_flow_data[-16:]

    # 3. Decrypt with AES-128-GCM
    decryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(iv, auth_tag)
    ).decryptor()

    decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    decrypted_json = json.loads(decrypted_bytes.decode("utf-8"))

    return decrypted_json, aes_key, iv


def encrypt_flow_response(response_data: dict, aes_key: bytes, initial_vector: bytes) -> str:
    """
    Encrypts the response to a WhatsApp Flow request according to Meta specification:
    1. Bitwise inverts the original initial_vector bytes (~b & 0xFF).
    2. Encrypts response payload using AES-128-GCM with the flipped IV.
    3. Appends auth tag to ciphertext and base64 encodes the result.
    Returns: base64 encoded string.
    """
    # Bitwise NOT on every byte of original IV
    flipped_iv = bytes(~b & 0xFF for b in initial_vector)

    plaintext = json.dumps(response_data, separators=(",", ":")).encode("utf-8")

    encryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(flipped_iv)
    ).encryptor()

    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    auth_tag = encryptor.tag

    # Response is ciphertext + tag base64 encoded
    encrypted_bytes = ciphertext + auth_tag
    return base64.b64encode(encrypted_bytes).decode("utf-8")
