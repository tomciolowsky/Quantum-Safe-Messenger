import sys
import time
import httpx2

from qsm.crypto import (
    HybridParty,
    bytes_to_upperhex,
    dict_to_package,
    package_to_dict,
    upperhex_to_bytes,
)

API_URL = "http://127.0.0.1:8000"

def log_demo_step(step_number: int, title: str, details: str = ""):
    print(f"\n{'=' * 105}\n")
    print(f"[{step_number}] : {title}")
    if details:
        print(f"  --> {details}")
    print(f"\n{'=' * 105}\n")

def run_demo():
    print(f"\n{'=' * 105}")
    print(f"\n    QUANTUM-SAFE MESSENGER (QSM) - POST-QUANTUM RELAY DEMO")
    print(f"\n    Standards: FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), AES-256-GCM")
    print(f"\n{'=' * 105}\n")

    try:
        response = httpx2.get(f"{API_URL}/health/info")
        response.raise_for_status()
        print(f"[+] Connected to QSM API at: {API_URL}")
        print(f"    Server status: {response.json().get('status')}")
    except Exception as e:
        print(f"[!] Failed to connect to QSM API at: {API_URL}")
        print(f"    Error: {e}")
        print(f"    Use: 'uvicorn qsm.api.main:app --reload' OR 'docker compose up'")
        sys.exit(1)

    hybrid = HybridParty()
    pseudo_random_suffix = int(time.time())%1000
    alice_username = f"alice_{pseudo_random_suffix}"
    bob_username = f"bob_{pseudo_random_suffix}"

    log_demo_step(1, "KEY GENERATION", "Takes place locally on each party's machine.")
    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    print(f"[Alice] Generated ML-KEM-768 and ML-DSA-65 Key Pair")
    print(f"[Alice] ML-KEM-768 Public Key Length: {len(alice_keys.kem.public_key)} Bytes")
    print(f"[Alice] ML-DSA-65 Public Key Length: {len(alice_keys.dsa.public_key)} Bytes")

    print(f"[Bob] Generated ML-KEM-768 and ML-DSA-65 Key Pair")
    print(f"[Bob] ML-KEM-768 Public Key Length: {len(bob_keys.kem.public_key)} Bytes")
    print(f"[Bob] ML-DSA-65 Public Key Length: {len(bob_keys.dsa.public_key)} Bytes")

    log_demo_step(2, "USER & KEYS REGISTRATION", "Only the public keys are stored on the server!")
    with httpx2.Client(base_url=API_URL) as client:
        alice_registration_response = client.post(
            "/users/register",
            json={
                "username": alice_username,
                "kem_public_key": bytes_to_upperhex(alice_keys.kem.public_key),
                "dsa_public_key": bytes_to_upperhex(alice_keys.dsa.public_key)
            }
        )
        alice_registration_response.raise_for_status()
        print(f"[Alice] Registered the user: {alice_username}")

        bob_registration_response = client.post(
            "/users/register",
            json={
                "username": bob_username,
                "kem_public_key": bytes_to_upperhex(bob_keys.kem.public_key),
                "dsa_public_key": bytes_to_upperhex(bob_keys.dsa.public_key)
            }
        )
        bob_registration_response.raise_for_status()
        print(f"[Bob] Registered the user: {bob_username}")

        log_demo_step(3, "MESSAGE ENCRYPTION & SIGNING", "Server only sees the encrypted package, not the plaintext and secret keys.")
        bob_keys_response = client.get(f"/users/{bob_username}/keys")
        bob_keys_response_data = bob_keys_response.json()
        print(f"[Alice] Retrieved {bob_username}'s public KEM and DSA keys from the server.")

        secret_message = b"This is a secret message from Alice to Bob 123!"
        print(f"[Alice] Alice's Secret Message to encrypt: '{secret_message.decode()}'")

        package = hybrid.encrypt_package(
            receiver_kem_pk=upperhex_to_bytes(bob_keys_response_data["kem_public_key"]),
            sender_dsa_sk=alice_keys.dsa.secret_key,
            plaintext=secret_message
        )
        print(f"[Alice] 1. KEM Encapsulation: Generated a *shared secret* and *KEM ciphertext* using Bob's public KEM key.")
        print(f"[Alice] 2. AES-GCM Encryption: Encrypted the secret message with AES-GCM using *shared secret* and random *nonce*.")
        print(f"[Alice] 3. DSA Signature: Signed the package (*KEM ciphertext* + *nonce* + *encrypted message*) with Alice's private DSA key.")

        log_demo_step(4, "MESSAGE SENDING", "Server only sees the encrypted package - meaningless upper-hex encoded bytes.")
        package_dict = package_to_dict(package)
        send_message_response = client.post(
            f"/messages/send",
            headers={"X-Username-Header": alice_username},
            json={
                "receiver_username": bob_username,
                "package": package_dict
            }
        )
        send_message_response_data = send_message_response.json()
        message_id = send_message_response_data.get("id")
        message_status = send_message_response_data.get("status")
        print(f"[Server] Message registered with ID: {message_id}, status: {message_status}")

        log_demo_step(5, "MESSAGE RETRIEVAL", "Server only sees the encrypted package - meaningless upper-hex encoded bytes.")
        inbox_response = client.get(
            f"/messages/inbox",
            headers={"X-Username-Header": bob_username}
        )
        inbox_response_data = inbox_response.json()
        print(f"[Bob] Retrieved {len(inbox_response_data)} message(s) from the server.")

        sender_username = inbox_response_data[0].get("sender_username")
        print(f"[Bob] Retrieved message sender is: {sender_username}")

        log_demo_step(6, "MESSAGE DECRYPTION & VERIFICATION", "Takes place locally on Bob's machine.")

        alice_keys_response = client.get(f"/users/{sender_username}/keys")
        alice_keys_response_data = alice_keys_response.json()
        print(f"[Bob] Retrieved {sender_username}'s public KEM and DSA keys from the server.")
        
        received_package_dict = inbox_response_data[0].get("package")
        received_package = dict_to_package(received_package_dict)

        decrypted_message = hybrid.decrypt_package(
            receiver_kem_sk=bob_keys.kem.secret_key,
            sender_dsa_pk=upperhex_to_bytes(alice_keys_response_data["dsa_public_key"]),
            package=received_package
        )
        print(f"[Bob] 1. DSA Signature: Verified the signature with Alice's public DSA key.")
        print(f"[Bob] 2. KEM Decapsulation: Retrieved the *shared secret* using Bob's private KEM key.")
        print(f"[Bob] 3. AES-GCM Encryption: Decrypted the secret message with AES-GCM using *shared secret* and *nonce*.")

        print(f"[Bob] Decrypted Message: '{decrypted_message.decode()}'")

        log_demo_step(7, "MESSAGE ACKNOWLEDGEMENT", "Server only sees the message ID and changes its status to READ.")
        client.post(
            f"/messages/{message_id}/acknowledge",
            headers={"X-Username-Header": bob_username}
        )
        print(f"[Bob] Acknowledged the message with ID: {message_id} - status changed to READ.")

    print(f"\n{'#' * 105}")
    print(f"DEMO COMPLETED SUCCESSFULLY!")
    print(f"{'#' * 105}\n")

if __name__ == "__main__":
    run_demo()