"""Authentication dependencies and role-based access control."""
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Farm, RevokedToken, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_token_payload(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        return decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    if db.get(RevokedToken, payload.get("jti", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been signed out")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This area is restricted to: {', '.join(roles)}")
        return user

    return checker


def can_view_farm(user: User, farm: Farm) -> bool:
    if user.role == "admin" or farm.user_id == user.id:
        return True
    # Organisation staff may view farms whose owners are members of their organisation.
    if user.role == "organisation" and user.organisation_id is not None:
        return farm.owner is not None and farm.owner.organisation_id == user.organisation_id
    return False


def can_edit_farm(user: User, farm: Farm) -> bool:
    return user.role == "admin" or farm.user_id == user.id


def get_farm_for_user(farm_id: int, db: Session, user: User, write: bool = False) -> Farm:
    farm = db.get(Farm, farm_id)
    # Return 404 for both missing and unauthorised farms to avoid leaking existence.
    if farm is None or not can_view_farm(user, farm):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found")
    if write and not can_edit_farm(user, farm):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can view this farm but not modify it")
    return farm
