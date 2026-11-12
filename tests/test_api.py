import asyncio

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from qsm.api import app
from qsm.crypto import (
    HybridParty,
    UserCryptoKeys,
    bytes_to_upperhex,
    dict_to_package,
    package_to_dict,
    upperhex_to_bytes,
)
from qsm.storage import Base, get_db


async def _run_schema_op(engine, op_name: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(getattr(Base.metadata, op_name))
    await engine.dispose()


def _register_user(client: TestClient, hybrid: HybridParty, username: str) -> UserCryptoKeys:
    keys = hybrid.generate_keys()
    response = client.post(
        "/users/register",
        json={
            "username": username,
            "kem_public_key": bytes_to_upperhex(keys.kem.public_key),
            "dsa_public_key": bytes_to_upperhex(keys.dsa.public_key),
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return keys


@pytest.fixture(autouse=True)
def setup_database(tmp_path):
    """
    Create an isolated per-test async SQLite database and override get_db.
    """
    test_db_url = f"sqlite+aiosqlite:///{tmp_path / 'test_qsm.db'}"
    test_engine = create_async_engine(test_db_url, poolclass=NullPool)
    testing_session_local = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with testing_session_local() as db:
            yield db

    asyncio.run(_run_schema_op(test_engine, "create_all"))
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        asyncio.run(_run_schema_op(test_engine, "drop_all"))


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.
    """
    return TestClient(app)


def test_full_qsm_lifecycle(client):
    hybrid = HybridParty()

    alice_keys = _register_user(client, hybrid, "alice")
    bob_keys = _register_user(client, hybrid, "bob")

    bob_keys_response = client.get("/users/bob/keys")
    assert bob_keys_response.status_code == status.HTTP_200_OK
    bob_keys_data = bob_keys_response.json()
    assert bob_keys_data["kem_public_key"] == bytes_to_upperhex(bob_keys.kem.public_key)

    test_secret_message = b"This is a secret message from Alice to Bob 123!"
    test_package = hybrid.encrypt_package(
        receiver_kem_pk=upperhex_to_bytes(bob_keys_data["kem_public_key"]),
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=test_secret_message,
    )

    send_message_response = client.post(
        "/messages/send",
        headers={"X-Username-Header": "alice"},
        json={
            "receiver_username": "bob",
            "package": package_to_dict(test_package),
        },
    )
    assert send_message_response.status_code == status.HTTP_201_CREATED
    alice_message_id = send_message_response.json()["id"]

    inbox_response = client.get(
        "/messages/inbox",
        headers={"X-Username-Header": "bob"},
    )
    assert inbox_response.status_code == status.HTTP_200_OK

    inbox_data = inbox_response.json()
    assert len(inbox_data) == 1

    received_message = inbox_data[0]
    assert received_message["sender_username"] == "alice"
    assert received_message["id"] == alice_message_id

    alice_keys_response = client.get(f"/users/{received_message['sender_username']}/keys")
    assert alice_keys_response.status_code == status.HTTP_200_OK
    alice_keys_data = alice_keys_response.json()

    received_package = dict_to_package(received_message["package"])
    decrypted_message = hybrid.decrypt_package(
        receiver_kem_sk=bob_keys.kem.secret_key,
        sender_dsa_pk=upperhex_to_bytes(alice_keys_data["dsa_public_key"]),
        package=received_package,
    )
    assert decrypted_message == test_secret_message

    acknowledge_response = client.post(
        f"/messages/{received_message['id']}/acknowledge",
        headers={"X-Username-Header": "bob"},
    )
    assert acknowledge_response.status_code == status.HTTP_200_OK

    read_inbox = client.get(
        "/messages/inbox",
        params={"status": "READ"},
        headers={"X-Username-Header": "bob"},
    )
    assert read_inbox.status_code == status.HTTP_200_OK
    assert [msg["id"] for msg in read_inbox.json()] == [alice_message_id]


def test_register_duplicate_user_returns_400(client):
    hybrid = HybridParty()
    _register_user(client, hybrid, "alice")
    duplicate_keys = hybrid.generate_keys()

    response = client.post(
        "/users/register",
        json={
            "username": "alice",
            "kem_public_key": bytes_to_upperhex(duplicate_keys.kem.public_key),
            "dsa_public_key": bytes_to_upperhex(duplicate_keys.dsa.public_key),
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_get_keys_unknown_user_returns_404(client):
    response = client.get("/users/missing_user/keys")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_send_message_validation_errors(client):
    hybrid = HybridParty()
    alice_keys = _register_user(client, hybrid, "alice")
    package = hybrid.encrypt_package(
        receiver_kem_pk=alice_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=b"Validation check",
    )
    package_dict = package_to_dict(package)

    missing_receiver_resp = client.post(
        "/messages/send",
        headers={"X-Username-Header": "alice"},
        json={"receiver_username": "ghost", "package": package_dict},
    )
    assert missing_receiver_resp.status_code == status.HTTP_404_NOT_FOUND

    self_send_resp = client.post(
        "/messages/send",
        headers={"X-Username-Header": "alice"},
        json={"receiver_username": "alice", "package": package_dict},
    )
    assert self_send_resp.status_code == status.HTTP_400_BAD_REQUEST


def test_acknowledge_validation_and_inbox_status_filtering(client):
    hybrid = HybridParty()
    alice_keys = _register_user(client, hybrid, "alice")
    bob_keys = _register_user(client, hybrid, "bob")

    missing_ack = client.post("/messages/999/acknowledge", headers={"X-Username-Header": "bob"})
    assert missing_ack.status_code == status.HTTP_404_NOT_FOUND

    package = hybrid.encrypt_package(
        receiver_kem_pk=bob_keys.kem.public_key,
        sender_dsa_sk=alice_keys.dsa.secret_key,
        plaintext=b"State machine check",
    )
    send_resp = client.post(
        "/messages/send",
        headers={"X-Username-Header": "alice"},
        json={"receiver_username": "bob", "package": package_to_dict(package)},
    )
    assert send_resp.status_code == status.HTTP_201_CREATED
    msg_id = send_resp.json()["id"]

    # Cannot acknowledge while still PENDING
    early_ack = client.post(f"/messages/{msg_id}/acknowledge", headers={"X-Username-Header": "bob"})
    assert early_ack.status_code == status.HTTP_400_BAD_REQUEST

    # Delivered inbox is empty prior to initial PENDING retrieval
    delivered_before = client.get(
        "/messages/inbox",
        params={"status": "DELIVERED"},
        headers={"X-Username-Header": "bob"},
    )
    assert delivered_before.status_code == status.HTTP_200_OK
    assert delivered_before.json() == []

    # First default fetch returns PENDING and transitions to DELIVERED
    pending_fetch = client.get("/messages/inbox", headers={"X-Username-Header": "bob"})
    assert pending_fetch.status_code == status.HTTP_200_OK
    assert len(pending_fetch.json()) == 1

    delivered_after = client.get(
        "/messages/inbox",
        params={"status": "DELIVERED"},
        headers={"X-Username-Header": "bob"},
    )
    assert delivered_after.status_code == status.HTTP_200_OK
    assert len(delivered_after.json()) == 1

    # Wrong user cannot acknowledge Bob's message
    wrong_user_ack = client.post(f"/messages/{msg_id}/acknowledge", headers={"X-Username-Header": "alice"})
    assert wrong_user_ack.status_code == status.HTTP_404_NOT_FOUND

    # Bob acknowledges once -> READ
    ok_ack = client.post(f"/messages/{msg_id}/acknowledge", headers={"X-Username-Header": "bob"})
    assert ok_ack.status_code == status.HTTP_200_OK

    # Second acknowledge fails because message is already READ
    repeat_ack = client.post(f"/messages/{msg_id}/acknowledge", headers={"X-Username-Header": "bob"})
    assert repeat_ack.status_code == status.HTTP_400_BAD_REQUEST


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
        "Package Decryption (KEM decapsulation + AES decryption + DSA verification)",
    ]
    assert len(operations) == len(expected_operations)
    for expected_operation in expected_operations:
        assert expected_operation in operations
