import pytest
from qsm.crypto import (
    HybridParty, 
    EncryptedPackage,
    package_to_dict,
    dict_to_package
)


def test_hybrid_encryption_decryption():
    hybrid = HybridParty()

    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    test_message = b"This is a test message 123!"

    test_package = hybrid.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=test_message
    )

    test_decrypted = hybrid.decrypt_package(
        receiver_kem_sk=bob_keys.kem.secret_key,
        sender_dsa_pk=alice_keys.dsa.public_key,
        package=test_package
    )

    assert test_decrypted == test_message

def test_serialization_deserialization():
    hybrid = HybridParty()

    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    test_message = b"This is a test message 123!"

    test_package = hybrid.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=test_message
    )

    serialized_package = package_to_dict(test_package)
    deserialized_package = dict_to_package(serialized_package)

    assert test_package == deserialized_package

def test_invalid_signature():
    hybrid = HybridParty()

    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    test_message = b"This is a test message 123!"

    test_package = hybrid.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=test_message
    )

    tampered_signature = bytearray(test_package.signature)
    tampered_signature[0] ^= 0xFF  # Flip the first byte
    
    tampered_package = EncryptedPackage(
        kem_ciphertext=test_package.kem_ciphertext,
        nonce=test_package.nonce,
        encrypted_payload=test_package.encrypted_payload,
        signature=bytes(tampered_signature)
    )

    with pytest.raises(ValueError):
        hybrid.decrypt_package(
            receiver_kem_sk=bob_keys.kem.secret_key,
            sender_dsa_pk=alice_keys.dsa.public_key,
            package=tampered_package
        )