
from .hybrid import EncryptedPackage


def bytes_to_upperhex(data: bytes) -> str:
    """
    Converts bytes to an uppercase hexadecimal string.
    """
    return data.hex().upper()

def upperhex_to_bytes(data: str) -> bytes:
    """
    Converts an uppercase hexadecimal string to bytes.
    """
    return bytes.fromhex(data)

def package_to_dict(package: EncryptedPackage) -> dict:
    """
    Converts an EncryptedPackage to a dictionary with uppercase hexadecimal strings.
    """
    return {
        "kem_ciphertext": bytes_to_upperhex(package.kem_ciphertext),
        "nonce": bytes_to_upperhex(package.nonce),
        "encrypted_payload": bytes_to_upperhex(package.encrypted_payload),
        "signature": bytes_to_upperhex(package.signature)
    }

def dict_to_package(data: dict[str, str]) -> EncryptedPackage:
    """
    Converts a dictionary with uppercase hexadecimal strings to an EncryptedPackage.
    """
    return EncryptedPackage(
        kem_ciphertext=upperhex_to_bytes(data["kem_ciphertext"]),
        nonce=upperhex_to_bytes(data["nonce"]),
        encrypted_payload=upperhex_to_bytes(data["encrypted_payload"]),
        signature=upperhex_to_bytes(data["signature"])
    )