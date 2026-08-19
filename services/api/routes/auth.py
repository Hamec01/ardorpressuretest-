from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from services.api.auth import create_access_token, get_current_user, require_role, verify_password
from services.api.database import get_db
from services.api.models import User
from services.api.audit import log_audit_event

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str
    role: str
    email: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Аутентификация пользователя и выдача JWT токена."""
    user = db.query(User).filter(User.username == req.username.strip(), User.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    })

    log_audit_event(
        db,
        entity_type="user",
        entity_id=str(user.id),
        action="login",
        actor_id=str(user.id),
        actor_name=user.full_name,
        details={"ip": "local", "role": user.role}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(require_role(["operator", "foreman", "admin"]))):
    """Возвращает профиль текущего пользователя."""
    return user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    user: User = Depends(require_role(["admin", "foreman"])),
    db: Session = Depends(get_db)
):
    """Список пользователей системы (доступно для Admin и Foreman)."""
    return db.query(User).filter(User.is_active == True).all()
