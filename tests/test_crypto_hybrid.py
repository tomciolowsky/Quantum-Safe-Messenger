import pytest

from qsm.crypto import EncryptedPackage, HybridParty, dict_to_package, package_to_dict


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


@pytest.mark.parametrize("field_name", ["kem_ciphertext", "nonce", "encrypted_payload"])
def test_tampered_package_fields_rejected(field_name: str):
    hybrid = HybridParty()

    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    test_package = hybrid.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=b"Integrity check payload",
    )

    tampered_bytes = bytearray(getattr(test_package, field_name))
    tampered_bytes[0] ^= 0xFF

    tampered_kwargs = {
        "kem_ciphertext": test_package.kem_ciphertext,
        "nonce": test_package.nonce,
        "encrypted_payload": test_package.encrypted_payload,
        "signature": test_package.signature,
        field_name: bytes(tampered_bytes),
    }

    with pytest.raises(ValueError):
        hybrid.decrypt_package(
            receiver_kem_sk=bob_keys.kem.secret_key,
            sender_dsa_pk=alice_keys.dsa.public_key,
            package=EncryptedPackage(**tampered_kwargs),
        )


def test_context_mismatch_fails():
    sender_party = HybridParty(context=b"qsm-v1")
    receiver_party = HybridParty(context=b"qsm-v2")

    alice_keys = sender_party.generate_keys()
    bob_keys = receiver_party.generate_keys()

    package = sender_party.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=b"Domain separation test",
    )

    with pytest.raises(ValueError, match="Invalid signature"):
        receiver_party.decrypt_package(
            receiver_kem_sk=bob_keys.kem.secret_key,
            sender_dsa_pk=alice_keys.dsa.public_key,
            package=package,
        )
