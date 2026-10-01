import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from qsm.crypto import HybridParty, bytes_to_upperhex, package_to_dict
from qsm.storage import Base, User, UserPublicKey, EncryptedMessage, MessageStatus


@pytest.fixture
def create_test_session():
    """
    Creates a temporary in-memory SQLite database for testing.
    """
    test_engine = create_engine("sqlite:///:memory:", echo=True)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    test_db = TestingSessionLocal()
    try:
        yield test_db
    finally:
        test_db.close()
    Base.metadata.drop_all(bind=test_engine)



def test_create_user(create_test_session):
    """
    Test creating a new user in the database.
    """
    db = create_test_session
    test_user = User(username="testuser1")
    db.add(test_user)
    db.commit()
    
    stmt = select(User).where(User.username == "testuser1")
    result = db.scalars(stmt).first()

    assert result is not None
    assert result.username == "testuser1"


def test_user_public_key_relation(create_test_session):
    """
    Test the relationship between User and UserPublicKey.
    """
    hybrid = HybridParty()
    test_keys = hybrid.generate_keys()

    db = create_test_session
    test_user = User(username="testuser1")
    db.add(test_user)
    db.commit()

    test_public_key = UserPublicKey(
        user_id=test_user.id,
        kem_public_key=bytes_to_upperhex(test_keys.kem.public_key),
        dsa_public_key=bytes_to_upperhex(test_keys.dsa.public_key),
        algorithm_info="ML_KEM_768 + ML_DSA_65"
    )
    db.add(test_public_key)
    db.commit()

    stmt = select(User, UserPublicKey).join(UserPublicKey.user)
    result = db.execute(stmt).first()
    
    assert result.User is not None
    assert result.UserPublicKey is not None
    assert result.User.id == result.UserPublicKey.user_id
    assert result.UserPublicKey.kem_public_key == bytes_to_upperhex(test_keys.kem.public_key)
    assert result.UserPublicKey.dsa_public_key == bytes_to_upperhex(test_keys.dsa.public_key)


def test_encrypted_message_flow(create_test_session):
    """
    Test the flow of sending and receiving an encrypted message between two users.
    """
    hybrid = HybridParty()
    alice_keys = hybrid.generate_keys()
    bob_keys = hybrid.generate_keys()

    db = create_test_session
    alice_user = User(username="alice")
    bob_user = User(username="bob")
    db.add_all([alice_user, bob_user])
    db.commit()

    test_plaintext = b"This is a secret message!"

    test_package = hybrid.encrypt_package(
        receiver_kem_pk = bob_keys.kem.public_key,
        sender_dsa_sk = alice_keys.dsa.secret_key,
        plaintext = test_plaintext
    )

    test_package_dict = package_to_dict(test_package)

    test_encrypted_message = EncryptedMessage(
        sender_id=alice_user.id,
        receiver_id=bob_user.id,
        kem_ciphertext=test_package_dict['kem_ciphertext'],
        nonce=test_package_dict['nonce'],
        encrypted_payload=test_package_dict['encrypted_payload'],
        signature=test_package_dict['signature'],
        status=MessageStatus.PENDING
    )
    db.add(test_encrypted_message)
    db.commit()

    stmt = select(EncryptedMessage).where(
        EncryptedMessage.receiver_id == bob_user.id,
        EncryptedMessage.status == MessageStatus.PENDING
    )
    result = db.scalars(stmt).all()

    assert len(result) == 1
    assert result[0].sender.username == "alice" 
    assert result[0].encrypted_payload == test_package_dict['encrypted_payload']