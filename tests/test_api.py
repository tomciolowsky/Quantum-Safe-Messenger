import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from qsm.api import app
from qsm.storage import get_db, Base
from fastapi import status
from qsm.crypto import (
    HybridParty,
    bytes_to_upperhex,
    upperhex_to_bytes,
    dict_to_package,
    package_to_dict
)


test_engine = create_engine("sqlite:///:memory:",
                            poolclass=StaticPool,
                            connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

def override_get_db():
    """
    Override the get_db dependency to use an in-memory SQLite database for testing.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """
    Before each test, create the database schema in the in-memory SQLite database.
    Delete it afterwards.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.
    """
    return TestClient(app)


def test_full_qsm_lifecycle(client):
    hybrid = HybridParty()

    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    alice_register_response = client.post("/users/register", json={
        "username": "alice",
        "kem_public_key": bytes_to_upperhex(alice_keys.kem.public_key),
        "dsa_public_key": bytes_to_upperhex(alice_keys.dsa.public_key)
    })

    assert alice_register_response.status_code == status.HTTP_201_CREATED

    bob_register_response = client.post("/users/register", json={
        "username": "bob",
        "kem_public_key": bytes_to_upperhex(bob_keys.kem.public_key),
        "dsa_public_key": bytes_to_upperhex(bob_keys.dsa.public_key)
    })

    assert bob_register_response.status_code == status.HTTP_201_CREATED

    bob_keys_response = client.get("users/bob/keys")
    assert bob_keys_response.status_code == status.HTTP_200_OK
    
    bob_keys_data = bob_keys_response.json()

    test_secret_message = b"This is a secret message from Alice to Bob 123!"
    test_package = hybrid.encrypt_package(
        receiver_kem_pk=upperhex_to_bytes(bob_keys_data["kem_public_key"]),
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=test_secret_message
    )
    test_package_dict = package_to_dict(test_package)

    send_message_response = client.post(
        "/messages/send",
        headers={"X-Username-Header": "alice"},
        json={
            "receiver_username": "bob",
            "package": test_package_dict
        }
    )

    assert send_message_response.status_code == status.HTTP_201_CREATED
    alice_message_id = send_message_response.json()["id"]

    inbox_response = client.get(
        "/messages/inbox",
        headers={"X-Username-Header": "bob"}
    )

    assert inbox_response.status_code == status.HTTP_200_OK
    
    inbox_data = inbox_response.json()
    assert len(inbox_data) == 1

    received_message = inbox_data[0]
    assert received_message["sender_username"] == "alice"
    assert received_message["id"] == alice_message_id

    alice_keys_response = client.get(f"users/{received_message["sender_username"]}/keys")
    alice_keys_data = alice_keys_response.json()

    received_package_dict = received_message["package"]
    received_package = dict_to_package(received_package_dict)
    decrypted_message = hybrid.decrypt_package(
        receiver_kem_sk=bob_keys.kem.secret_key,
        sender_dsa_pk=upperhex_to_bytes(alice_keys_data["dsa_public_key"]),
        package=received_package
    )

    assert decrypted_message == test_secret_message

    acknowledge_response = client.post(
        f"/messages/{received_message['id']}/acknowledge",
        headers={"X-Username-Header": "bob"}
    )

    assert acknowledge_response.status_code == status.HTTP_200_OK


def test_health_check_endpoint(client):
    """
    Test the /health/info endpoint to ensure it returns a valid response.
    """
    response = client.get("/health/info")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Quantum-Safe Messenger API"
    assert "supported_standards" in data

def test_benchmark_endpoint(client):
    """
    Test the /health/benchmark endpoint to ensure it returns a valid response.
    """
    response = client.get("/health/benchmark")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    results = data.get("results", [])
    
    operations = [result["operation"] for result in results]
    expected_operations = [
        "Key Pair Generation (KEM + DSA)",
        "Package Encryption (KEM encapsulation + AES encryption + DSA signing)",
        "Package Decryption (KEM decapsulation + AES decryption + DSA verification)"
    ]
    assert len(operations) == len(expected_operations)
    for expected_operation in expected_operations:
        assert expected_operation in operations