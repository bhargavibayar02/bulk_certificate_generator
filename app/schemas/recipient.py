"""
Recipient Pydantic Schemas.

Defines schemas and strong validation for certificate recipients.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientCreate(BaseModel):
    """
    Schema for an individual recipient in a bulk generation request.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full name of the recipient to appear on the certificate."
    )
    email: EmailStr = Field(
        ...,
        max_length=254,
        description="Valid recipient email address."
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """
        Trim whitespace and ensure name is not empty or whitespace-only.
        """
        if not isinstance(value, str):
            raise ValueError("Recipient name must be a string")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Recipient name cannot be empty or whitespace only")
        return trimmed

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """
        Trim and normalize email address string before EmailStr validation.
        """
        if isinstance(value, str):
            return value.strip()
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Bhargavi Bayar",
                "email": "bhargavi@example.com"
            }
        }
    }
