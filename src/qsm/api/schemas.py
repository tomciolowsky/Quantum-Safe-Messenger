from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EncryptedPackageSchema(BaseModel):
    """
    Schema for an encrypted package with fields in uppercase hexadecimal format.
    """
    kem_ciphertext: str = Field(..., description="The ML-KEM ciphertext in upperhex format.")
    nonce: str = Field(..., description="The AESGCM nonce in upperhex format.")
    encrypted_payload: str = Field(..., description="The encrypted payload in upperhex format.")
    signature: str = Field(..., description="The ML-DSA signature in upperhex format.")


class UserRegistrationRequestSchema(BaseModel):
    """
    Schema for user registration request with public keys.
    """
    username: str = Field(..., min_length=3, max_length=32, pattern="^[a-zA-Z0-9_-]+$", description="The username of the user.")
    kem_public_key: str = Field(..., description="The ML-KEM public key in upperhex format.")
    dsa_public_key: str = Field(..., description="The ML-DSA public key in upperhex format.")
    algorithm_info: str | None = "ML_KEM_768 + ML_DSA_65"


class UserResponseSchema(BaseModel):
    """
    Basic data about a user.
    """
    id: int
    username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicKeyResponseSchema(BaseModel):
    """
    Schema for a response containing a user's public keys.
    """
    username: str
    kem_public_key: str
    dsa_public_key: str
    algorithm_info: str
    created_at: datetime


class SendMessageRequestSchema(BaseModel):
    """
    Request schema for sending an encrypted message.
    """
    receiver_username: str = Field(..., description="The username of the message receiver.")
    package: EncryptedPackageSchema


class MessageResponseSchema(BaseModel):
    """
    Response schema for an encrypted message.
    """
    id: int
    sender_username: str
    receiver_username: str
    package: EncryptedPackageSchema
    status: str
    created_at: datetime


class BenchmarkResultSchema(BaseModel):
    """
    Schema for the result of a cryptographic benchmark.
    """
    algorithm: str
    operation: str
    duration_ms: float


class BenchmarkResponseSchema(BaseModel):
    """
    Response schema for the list of benchmark results.
    """
    results: list[BenchmarkResultSchema]