"""
Border Customization Pydantic Schemas.

Enforces strictly controlled design parameters for certificate borders:
- Style: none, single, double, thick
- Color: validated 3 or 6 digit hexadecimal string (e.g. #1E3A8A)
- Width: integer in safe range 1 to 10
"""
import enum
import re
from pydantic import BaseModel, Field, field_validator

HEX_COLOR_REGEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class BorderStyle(str, enum.Enum):
    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"
    THICK = "thick"


class BorderCustomization(BaseModel):
    """
    Controlled styling parameters for the certificate border.
    """
    border_style: BorderStyle = Field(
        default=BorderStyle.DOUBLE,
        description="Border style: 'none', 'single', 'double', or 'thick'."
    )
    border_color: str = Field(
        default="#1E3A8A",
        description="Hexadecimal color string for the border, e.g. #1E3A8A or #000."
    )
    border_width: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Border stroke width between 1 and 10 points."
    )

    @field_validator("border_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        """
        Validates hex color format (#RGB or #RRGGBB).
        Prevents arbitrary strings from reaching ReportLab drawing methods.
        """
        trimmed = value.strip()
        if not HEX_COLOR_REGEX.match(trimmed):
            raise ValueError(
                f"Invalid hex color format: '{value}'. Expected format like #1E3A8A or #333."
            )
        return trimmed.upper()
