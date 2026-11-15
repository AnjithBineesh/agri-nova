from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authentication.deps import get_current_user, get_token_payload
from ..authentication.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import Organisation, RevokedToken, User
from ..schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut, UserUpdate

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.organisation_name = user.organisation.name if user.organisation else None
    return out


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    org = None
    if body.organisation_name:
        org = db.scalar(select(Organisation).where(Organisation.name == body.organisation_name.strip()))
        if org is None:
            if body.role != "organisation":
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    "Organisation not found. Ask your organisation to register first.")
            org = Organisation(name=body.organisation_name.strip())
            db.add(org)
            db.flush()
    elif body.role == "organisation":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Organisation accounts need an organisation name")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password), role=body.role,
                organisation_id=org.id if org else None, preferences={})
    db.add(user)
    db.commit()
    db.refresh(user)
    token, expires = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, expires_at=expires, user=user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token, expires = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, expires_at=expires, user=user_out(user))


@router.post("/logout", status_code=204)
def logout(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    jti = payload.get("jti")
    if jti and not db.get(RevokedToken, jti):
        db.add(RevokedToken(jti=jti, expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)))
        db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name.strip()
    if body.preferences is not None:
        user.preferences = {**(user.preferences or {}), **body.preferences}
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
        user.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(user)
    return user_out(user)
