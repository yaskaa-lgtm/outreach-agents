"""Authentication payloads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=256)


class UserRead(BaseModel):
    email: str
    role: str
    is_demo: bool
