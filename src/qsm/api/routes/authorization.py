from fastapi import APIRouter, HTTPException, status
from qsm.api.dependencies import DBSession
from qsm.api.schemas import PublicKeyResponseSchema, UserResponseSchema, UserRegistrationRequestSchema
from qsm.storage import User, UserPublicKey
from sqlalchemy import select

router = APIRouter(
    prefix="/users",
    tags=["Users and Public Keys"],
)

@router.post("/register",
             response_model=UserResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Register a new user",
             description="Registers a new user with the provided username and public keys.")
def register_user(payload: UserRegistrationRequestSchema, db: DBSession):
    """
    Endpoint to register a new user and store their public ML-KEM and ML-DSA keys .
    """
    existing_user_stmt = select(User).where(User.username == payload.username)
    existing_user = db.scalars(existing_user_stmt).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username '{payload.username}' already exists."
        )

    new_user = User(username=payload.username)
    db.add(new_user)
    db.flush()

    user_public_key = UserPublicKey(
        user_id=new_user.id,
        kem_public_key=payload.kem_public_key,
        dsa_public_key=payload.dsa_public_key,
        algorithm_info=payload.algorithm_info
    )
    db.add(user_public_key)

    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/{username}/keys", 
            response_model=PublicKeyResponseSchema,
            status_code=status.HTTP_200_OK,
            summary="Retrieve user's public keys",
            description="Retrieves the public ML-KEM and ML-DSA keys for the specified username.")
def get_user_public_keys(username: str, db: DBSession):
    """
    Endpoint to retrieve a user's public keys by their username.
    """
    user_stmt = select(User).where(User.username == username)
    user = db.scalars(user_stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User '{username}' not found."
        )

    public_key_stmt = select(UserPublicKey).where(UserPublicKey.user_id == user.id)
    public_key = db.scalars(public_key_stmt).first()
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public keys for user '{username}' not found."
        )

    return PublicKeyResponseSchema(
        username=user.username,
        kem_public_key=public_key.kem_public_key,
        dsa_public_key=public_key.dsa_public_key,
        algorithm_info=public_key.algorithm_info,
        created_at=public_key.created_at
    )