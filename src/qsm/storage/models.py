from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def get_current_time() -> datetime:
    """
    Returns the current UTC time with timezone information.
    """
    return datetime.now(UTC)


class MessageStatus(str, PyEnum):
    """
    Enum representing the status of an encrypted message.
    """
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    READ = "READ"


class User(Base):
    """
    Represents a user in the system.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_current_time, nullable=False)

    # relations
    public_keys: Mapped[list[UserPublicKey]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sent_messages: Mapped[list[EncryptedMessage]] = relationship(foreign_keys="EncryptedMessage.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_messages: Mapped[list[EncryptedMessage]] = relationship(foreign_keys="EncryptedMessage.receiver_id", back_populates="receiver", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', created_at='{self.created_at}')>"


class UserPublicKey(Base):
    """
    Represents a public key associated with a user.
    """
    __tablename__ = "user_public_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    kem_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    dsa_public_key: Mapped[str] = mapped_column(Text, nullable=False)

    algorithm_info: Mapped[str] = mapped_column(String(50), default="ML_KEM_768 + ML_DSA_65", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_current_time, nullable=False)

    # relations
    user: Mapped[User] = relationship(back_populates="public_keys")
    
    def __repr__(self) -> str:
        return f"<UserPublicKey(id={self.id}, user_id={self.user_id}, algorithm='{self.algorithm_info}')>"


class EncryptedMessage(Base):
    """
    Represents an encrypted message sent from one user to another.
    """
    __tablename__ = "encrypted_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    kem_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.PENDING, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_current_time, nullable=False)

    # relations
    sender: Mapped[User] = relationship(foreign_keys=[sender_id], back_populates="")
    receiver: Mapped[User] = relationship(foreign_keys=[receiver_id], back_populates="")

    def __repr__(self) -> str:
        return f"<EncryptedMessage(id={self.id}, from={self.sender_id}, to={self.receiver_id}, created_at='{self.created_at}')>"