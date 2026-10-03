import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dilithium import CommunicationPartyDSA
from kyber import CommunicationPartyKEM


@dataclass(frozen=True)
class KeyPair:
    public_key: bytes
    secret_key: bytes

@dataclass(frozen=True)
class UserCryptoKeys:
    kem: KeyPair
    dsa: KeyPair

@dataclass(frozen=True)
class EncryptedPackage:
    kem_ciphertext: bytes
    nonce: bytes
    encrypted_payload: bytes
    signature: bytes


class HybridParty:
    """
    A party in the hybrid encryption scheme.
    Sends and receives packets securely using a combination of KEM, AESGCM and DSA.
    """
    def __init__(self,
                 kem_params="ML_KEM_768",
                 dsa_params="ML_DSA_65",
                 context: bytes = b""):
        
        self.kem = CommunicationPartyKEM(kem_params)
        self.dsa = CommunicationPartyDSA(dsa_params)
        self.context = context

    def generate_keys(self) -> UserCryptoKeys:
        """
        Generates a new set of KEM and DSA keys for a new user.
        """
        kem_pk, kem_sk = self.kem.key_generation()
        dsa_pk, dsa_sk = self.dsa.key_generation()

        return UserCryptoKeys(
            kem=KeyPair(public_key=kem_pk, secret_key=kem_sk),
            dsa=KeyPair(public_key=dsa_pk, secret_key=dsa_sk)
        )

    def encrypt_package(self,
                        receiver_kem_pk:bytes,
                        sender_dsa_sk:bytes,
                        plaintext:bytes) -> EncryptedPackage:
        """
        Encrypts a package using the hybrid encryption scheme:
        1. Establishes a *shared secret* using **ML-KEM**.
        2. Encrypts the *payload* using the *shared secret* and **AESGCM**.
        3. Signs the *package* (KEM ciphertext + nonce + encrypted payload) with **ML-DSA**.
        """
        shared_secret, kem_ciphertext = self.kem.encapsulate(receiver_kem_pk)

        aesgcm = AESGCM(shared_secret)
        nonce = os.urandom(12)
        aesgcm_encrypted_payload = aesgcm.encrypt(nonce, plaintext, None)

        data_to_sign = kem_ciphertext + nonce + aesgcm_encrypted_payload

        signature = self.dsa.signing(sender_dsa_sk, data_to_sign, ctx=self.context)

        return EncryptedPackage(
            kem_ciphertext=kem_ciphertext,
            nonce=nonce,
            encrypted_payload=aesgcm_encrypted_payload,
            signature=signature
        )

    def decrypt_package(self,
                        receiver_kem_sk:bytes,
                        sender_dsa_pk:bytes,
                        package:EncryptedPackage) -> bytes:
        """
        Decrypts a package using the hybrid encryption scheme:
        1. Verifies the **ML-DSA** signature of the *package*.
        2. Establishes the *shared secret* using **ML-KEM**.
        3. Decrypts the *payload* using the *shared secret* and **AESGCM**.
        """
        data_to_verify = package.kem_ciphertext + package.nonce + package.encrypted_payload

        is_valid = self.dsa.verify(sender_dsa_pk, data_to_verify, package.signature, ctx=self.context)

        if not is_valid:
            raise ValueError("Invalid signature")

        shared_secret = self.kem.decapsulate(receiver_kem_sk, package.kem_ciphertext)

        aesgcm = AESGCM(shared_secret)
        plaintext = aesgcm.decrypt(package.nonce, package.encrypted_payload, None)
        
        return plaintext