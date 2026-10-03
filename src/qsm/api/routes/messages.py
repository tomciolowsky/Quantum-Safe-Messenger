
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from qsm.api.dependencies import CurrentUser, DBSession
from qsm.api.schemas import (
    EncryptedPackageSchema,
    MessageResponseSchema,
    SendMessageRequestSchema,
)
from qsm.storage import EncryptedMessage, MessageStatus, User

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

@router.post("/send",
             response_model=MessageResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Send an encrypted message",
             description="Sends an encrypted message to the specified receiver.")
def send_message(
    payload: SendMessageRequestSchema,
    sender: CurrentUser,
    db: DBSession
):
    """
    Endpoint to send an encrypted message to a specified receiver.
    """
    receicer_stmt = select(User).where(User.username == payload.receiver_username)
    receiver = db.scalars(receicer_stmt).first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receiver '{payload.receiver_username}' not found."
        )

    if receiver.id == sender.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender and receiver cannot be the same user."
        )

    db_message = EncryptedMessage(
        sender_id=sender.id,
        receiver_id=receiver.id,
        kem_ciphertext=payload.package.kem_ciphertext,
        nonce=payload.package.nonce,
        encrypted_payload=payload.package.encrypted_payload,
        signature=payload.package.signature,
        status=MessageStatus.PENDING
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    return MessageResponseSchema(
        id=db_message.id,
        sender_username=sender.username,
        receiver_username=receiver.username,
        package=payload.package,
        status=db_message.status.value,
        created_at=db_message.created_at
    )


@router.get("/inbox",
            response_model=list[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
            summary="Retrieve received messages",
            description="Retrieves all messages received (status = PENDING) by the current user.")
def get_inbox(
    current_user: CurrentUser,
    db: DBSession
):
    """
    Endpoint to retrieve all messages received by the current user with status PENDING. 
    After retrieving them, automatically change their status to DELIVERED.
    """
    messages_stmt = select(EncryptedMessage).where(
        EncryptedMessage.receiver_id == current_user.id,
        EncryptedMessage.status == MessageStatus.PENDING
    ).order_by(EncryptedMessage.created_at.asc())
    messages = db.scalars(messages_stmt).all()

    response_messages = []
    for msg in messages:
        response_messages.append(
            MessageResponseSchema(
                id=msg.id,
                sender_username=msg.sender.username,
                receiver_username=current_user.username,
                package=EncryptedPackageSchema(
                    kem_ciphertext=msg.kem_ciphertext,
                    nonce=msg.nonce,
                    encrypted_payload=msg.encrypted_payload,
                    signature=msg.signature
                ),
                status=msg.status.value,
                created_at=msg.created_at
            )
        )
        msg.status = MessageStatus.DELIVERED

    db.commit()
    return response_messages


@router.post("/{message_id}/acknowledge",
                status_code=status.HTTP_200_OK,
                summary="Acknowledge a received message",
                description="Acknowledges a received message by changing its status to READ.")
def acknowledge_message(
    message_id: int,
    current_user: CurrentUser,
    db: DBSession
):
    """
    Endpoint to acknowledge a received message by changing its status to READ.
    """
    message_stmt = select(EncryptedMessage).where(
        EncryptedMessage.id == message_id,
        EncryptedMessage.receiver_id == current_user.id
    )
    message = db.scalars(message_stmt).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID '{message_id}' not found for the current user."
        )

    if message.status != MessageStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only messages with status DELIVERED can be acknowledged."
        )

    message.status = MessageStatus.READ
    db.commit()
    return {"message": f"Message with ID '{message_id}' acknowledged as READ."}