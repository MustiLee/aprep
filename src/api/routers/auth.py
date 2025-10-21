"""Authentication router - handles user registration, login, and password management."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    create_password_reset_token,
    create_email_verification_token,
    validate_password_strength,
)
from ...core.auth_dependencies import get_current_user, get_current_active_user
from ...models.db_models import User
from ...models.auth_schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
    VerifyEmailRequest,
    UserResponse,
    TokenResponse,
    LoginResponse,
    RegisterResponse,
    MessageResponse,
    ErrorResponse,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Constants
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCK_DURATION_MINUTES = 30


# ============================================================================
# REGISTRATION
# ============================================================================


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User registered successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
    },
)
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    This endpoint creates a new user account and sends an email verification link.

    - **email**: Valid email address
    - **password**: Password (min 8 characters, must include uppercase, lowercase, and number)
    - **full_name**: User's full name
    - **role**: Either 'student' or 'parent'
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Validate password strength
    is_valid, errors = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors},
        )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create email verification token
    email_token = create_email_verification_token()

    # Create user
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        email_verification_token=email_token,
        email_verification_sent_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # TODO: Send verification email
    # In production, this would send an email with the verification link
    logger.info(f"User registered: {new_user.email} (ID: {new_user.id})")
    logger.info(f"Email verification token: {email_token}")

    return RegisterResponse(
        user=UserResponse.model_validate(new_user),
        message="Registration successful. Please check your email to verify your account."
    )


# ============================================================================
# LOGIN
# ============================================================================


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {"description": "Login successful"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account locked or inactive"},
    },
)
async def login(
    login_data: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access and refresh tokens.

    - **email**: User's email address
    - **password**: User's password
    - **remember**: If true, refresh token has longer expiration
    """
    # Get user by email
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if account is locked
    if user.is_locked:
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is locked due to too many failed login attempts. Try again later.",
            )
        else:
            # Unlock account
            user.is_locked = False
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()

    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        # Increment failed login attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            # Lock account
            user.is_locked = True
            user.locked_until = datetime.utcnow() + timedelta(minutes=ACCOUNT_LOCK_DURATION_MINUTES)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed login attempts. Account locked for {ACCOUNT_LOCK_DURATION_MINUTES} minutes.",
            )

        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    # Reset failed login attempts
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()

    # Create access and refresh tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}

    access_token = create_access_token(token_data)

    # Refresh token expiration based on "remember me"
    refresh_expires = timedelta(days=30 if login_data.remember else settings.jwt_refresh_token_expire_days)
    refresh_token = create_refresh_token(token_data, expires_delta=refresh_expires)

    # Store refresh token
    user.refresh_token = refresh_token
    user.refresh_token_expires_at = datetime.utcnow() + refresh_expires

    db.commit()
    db.refresh(user)

    logger.info(f"User logged in: {user.email} (ID: {user.id})")

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        ),
        message="Login successful"
    )


# ============================================================================
# LOGOUT
# ============================================================================


@router.post(
    "/logout",
    response_model=MessageResponse,
    responses={
        200: {"description": "Logout successful"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout current user by invalidating refresh token.

    Requires valid access token in Authorization header.
    """
    # Invalidate refresh token
    current_user.refresh_token = None
    current_user.refresh_token_expires_at = None

    db.commit()

    logger.info(f"User logged out: {current_user.email} (ID: {current_user.id})")

    return MessageResponse(message="Logout successful")


# ============================================================================
# TOKEN REFRESH
# ============================================================================


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    - **refresh_token**: Valid refresh token from login
    """
    # Verify refresh token
    payload = verify_token(refresh_data.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get user from token
    user_id_str = payload.get("sub")
    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Verify stored refresh token matches
    if user.refresh_token != refresh_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check token expiration
    if user.refresh_token_expires_at and user.refresh_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Create new access token
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    new_access_token = create_access_token(token_data)

    logger.info(f"Token refreshed for user: {user.email} (ID: {user.id})")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_data.refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


# ============================================================================
# CURRENT USER
# ============================================================================


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"description": "Current user information"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.

    Requires valid access token in Authorization header.
    """
    return UserResponse.model_validate(current_user)


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    responses={
        200: {"description": "Email verified successfully"},
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def verify_email(
    verify_data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify user email address using verification token.

    - **token**: Email verification token from registration email
    """
    # Find user with this token
    user = db.query(User).filter(
        User.email_verification_token == verify_data.token
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    # Check if already verified
    if user.email_verified:
        return MessageResponse(message="Email already verified")

    # Verify email
    user.email_verified = True
    user.email_verification_token = None

    db.commit()

    logger.info(f"Email verified for user: {user.email} (ID: {user.id})")

    return MessageResponse(message="Email verified successfully")


# ============================================================================
# PASSWORD RESET
# ============================================================================


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    responses={
        200: {"description": "Password reset email sent"},
        404: {"model": ErrorResponse, "description": "Email not found"},
    },
)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset for user account.

    Sends password reset link to user's email.

    - **email**: User's email address
    """
    # Find user by email
    user = db.query(User).filter(User.email == forgot_data.email).first()

    # Don't reveal if email exists or not (security best practice)
    if not user:
        # Still return success to prevent email enumeration
        logger.warning(f"Password reset requested for non-existent email: {forgot_data.email}")
        return MessageResponse(
            message="If the email exists, a password reset link has been sent."
        )

    # Create password reset token
    reset_token = create_password_reset_token()
    user.password_reset_token = reset_token
    user.password_reset_expires_at = datetime.utcnow() + timedelta(
        hours=settings.password_reset_token_expire_hours
    )

    db.commit()

    # TODO: Send password reset email
    # In production, send email with reset link
    logger.info(f"Password reset requested for: {user.email} (ID: {user.id})")
    logger.info(f"Reset token: {reset_token}")

    return MessageResponse(
        message="If the email exists, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    responses={
        200: {"description": "Password reset successfully"},
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset user password using reset token.

    - **token**: Password reset token from email
    - **new_password**: New password (min 8 characters, must include uppercase, lowercase, and number)
    """
    # Find user with this reset token
    user = db.query(User).filter(
        User.password_reset_token == reset_data.token
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check token expiration
    if user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Validate new password
    is_valid, errors = validate_password_strength(reset_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors},
        )

    # Update password
    user.password_hash = hash_password(reset_data.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None

    # Reset failed login attempts
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None

    # Invalidate all refresh tokens for security
    user.refresh_token = None
    user.refresh_token_expires_at = None

    db.commit()

    logger.info(f"Password reset completed for user: {user.email} (ID: {user.id})")

    return MessageResponse(message="Password reset successfully. Please login with your new password.")
