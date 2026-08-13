from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import UserCreate, UserLogin, UserOut, Token, MessageResponse
from app.services import auth_service
from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new account.
    Returns a JWT access token immediately so the user is logged in right away.
    """
    try:
        user = auth_service.create_user(db, user_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    access_token = auth_service.create_access_token(data={"sub": user.id})
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.
    Returns a JWT access token on success.
    """
    user = auth_service.authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token(data={"sub": user.id})
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    Requires a valid Bearer token.
    """
    return UserOut.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
def logout():
    """
    Logout hint: client should delete the stored token.
    (JWT is stateless — server-side logout would require a token blacklist in Redis.)
    """
    return MessageResponse(message="Successfully logged out. Please delete your token.")
