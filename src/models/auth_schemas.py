"""Pydantic schemas for authentication endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================


class UserRegisterRequest(BaseModel):
    """User registration request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    role: str = Field(..., description="User role: student or parent")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is either student or parent."""
        if v not in ['student', 'parent']:
            raise ValueError('Role must be either "student" or "parent"')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "student@example.com",
                    "password": "SecurePass123",
                    "full_name": "John Doe",
                    "role": "student"
                }
            ]
        }
    }


class UserLoginRequest(BaseModel):
    """User login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember: bool = Field(default=False, description="Remember me option")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "student@example.com",
                    "password": "SecurePass123",
                    "remember": True
                }
            ]
        }
    }


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""

    email: EmailStr = Field(..., description="User email address")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "student@example.com"
                }
            ]
        }
    }


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(..., min_length=8, description="New password")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "reset_token_here",
                    "new_password": "NewSecurePass123"
                }
            ]
        }
    }


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str = Field(..., description="Refresh token")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "refresh_token": "refresh_token_here"
                }
            ]
        }
    }


class VerifyEmailRequest(BaseModel):
    """Email verification request schema."""

    token: str = Field(..., description="Email verification token")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "verification_token_here"
                }
            ]
        }
    }


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================


class UserResponse(BaseModel):
    """User response schema (public user information)."""

    id: UUID
    email: str
    full_name: str
    role: str
    email_verified: bool
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "student@example.com",
                    "full_name": "John Doe",
                    "role": "student",
                    "email_verified": True,
                    "is_active": True,
                    "created_at": "2025-10-20T12:00:00Z",
                    "last_login_at": "2025-10-20T14:30:00Z"
                }
            ]
        }
    }


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800
                }
            ]
        }
    }


class LoginResponse(BaseModel):
    """Login response schema."""

    user: UserResponse
    tokens: TokenResponse
    message: str = "Login successful"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "student@example.com",
                        "full_name": "John Doe",
                        "role": "student",
                        "email_verified": True,
                        "is_active": True,
                        "created_at": "2025-10-20T12:00:00Z",
                        "last_login_at": "2025-10-20T14:30:00Z"
                    },
                    "tokens": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 1800
                    },
                    "message": "Login successful"
                }
            ]
        }
    }


class RegisterResponse(BaseModel):
    """Registration response schema."""

    user: UserResponse
    message: str = "Registration successful. Please verify your email."

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "student@example.com",
                        "full_name": "John Doe",
                        "role": "student",
                        "email_verified": False,
                        "is_active": True,
                        "created_at": "2025-10-20T12:00:00Z",
                        "last_login_at": None
                    },
                    "message": "Registration successful. Please verify your email."
                }
            ]
        }
    }


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str
    success: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Operation completed successfully",
                    "success": True
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "Authentication failed",
                    "detail": "Invalid email or password",
                    "code": "INVALID_CREDENTIALS"
                }
            ]
        }
    }
