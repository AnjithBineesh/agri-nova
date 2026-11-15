from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..authentication.security import SELF_REGISTRABLE_ROLES


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "farmer"
    organisation_name: str | None = Field(default=None, max_length=200)

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in SELF_REGISTRABLE_ROLES:
            raise ValueError(f"role must be one of {', '.join(SELF_REGISTRABLE_ROLES)}")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    organisation_id: int | None
    organisation_name: str | None = None
    preferences: dict | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    preferences: dict | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
