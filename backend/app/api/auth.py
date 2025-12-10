"""
Authentication API endpoints with role-based access control
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from app.schemas.requests import LoginRequest
from app.schemas.responses import TokenResponse
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
from app.database import get_db
from app.models.database import User

router = APIRouter()
security = HTTPBearer()


# Request/Response schemas for user management
class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "user"  # master, admin, user


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """Dependency to get current user from JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.email == email).first()
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(current_user: User = Depends(get_current_user_from_token)) -> User:
    """Require admin or master role"""
    if current_user.role not in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_master(current_user: User = Depends(get_current_user_from_token)) -> User:
    """Require master role only"""
    if current_user.role != "master":
        raise HTTPException(status_code=403, detail="Master access required")
    return current_user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login"""
    user = db.query(User).filter(User.email == request.username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()

    access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


@router.get("/me")
def get_current_user(current_user: User = Depends(get_current_user_from_token)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active
    }


# ==================== Admin User Management ====================

@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users (admin/master only)"""
    # Admin can see all users except other admins/masters
    # Master can see everyone
    if current_user.role == "master":
        users = db.query(User).all()
    else:
        # Admin can only see regular users and themselves
        users = db.query(User).filter(
            (User.role == "user") | (User.id == current_user.id)
        ).all()
    return users


@router.post("/users", response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (admin/master only)"""
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Only master can create admin or master users
    if request.role in ["admin", "master"] and current_user.role != "master":
        raise HTTPException(status_code=403, detail="Only master can create admin/master users")

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role=request.role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a user (admin/master only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Admins cannot modify master users or other admins
    if current_user.role != "master" and user.role in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Cannot modify admin/master users")

    # Only master can change role to admin/master
    if request.role and request.role in ["admin", "master"] and current_user.role != "master":
        raise HTTPException(status_code=403, detail="Only master can assign admin/master roles")

    if request.email:
        # Check if new email is already taken
        existing = db.query(User).filter(User.email == request.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = request.email

    if request.password:
        user.hashed_password = hash_password(request.password)

    if request.full_name is not None:
        user.full_name = request.full_name

    if request.role:
        user.role = request.role

    if request.is_active is not None:
        user.is_active = request.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin/master only)"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Only master can delete admin/master users
    if user.role in ["master", "admin"] and current_user.role != "master":
        raise HTTPException(status_code=403, detail="Only master can delete admin/master users")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


# ==================== Initial Setup ====================

@router.post("/setup-master")
def setup_master_account(db: Session = Depends(get_db)):
    """
    One-time setup to create master account.
    Only works if no users exist in the database.
    """
    # Check if any users exist
    existing_users = db.query(User).count()
    if existing_users > 0:
        raise HTTPException(status_code=400, detail="Setup already completed. Users exist.")

    # Create master account with your credentials
    master_user = User(
        email="ryan@smamarketing.net",
        hashed_password=hash_password("NCH3250fl"),
        full_name="Ryan Shelley",
        role="master",
        is_active=True
    )
    db.add(master_user)
    db.commit()

    return {"message": "Master account created successfully", "email": "ryan@smamarketing.net"}

