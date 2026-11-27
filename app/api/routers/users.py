import re

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.services.user_service import UserService

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name must not be blank.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(cleaned):
            raise ValueError("Invalid email address.")
        return cleaned


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: str


@router.post("", response_model=UserResponse, status_code=201)
def create_user_endpoint(payload: CreateUserRequest, request: Request) -> UserResponse:
    service = UserService(
        db_provider=request.app.state.db_provider,
        clock_provider=request.app.state.clock_provider,
        id_provider=request.app.state.id_provider,
    )
    user = service.create_user(name=payload.name, email=payload.email)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email or "",
        created_at=user.created_at,
    )
