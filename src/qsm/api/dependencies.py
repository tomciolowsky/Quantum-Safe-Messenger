from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qsm.storage import User, get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    x_username_header: Annotated[str, Header(description="The username of the current user")],
    db: DBSession,
) -> User:
    """
    Dependency to retrieve the current user based on the provided 'X-Username-Header' header.
    Raises an HTTPException if the user is not found.
    """
    user_stmt = select(User).where(User.username == x_username_header)
    user = (await db.scalars(user_stmt)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{x_username_header}' not found.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
