from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.strip().lower()


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: str


class AskIn(BaseModel):
    question: str = Field(min_length=5, max_length=4000)
    conversation_id: int | None = None
    case_id: int | None = None
    translate_to: str | None = Field(default=None, max_length=3)
    doc_types: list[str] | None = None
    as_of: date | None = None
    include_historical: bool = False


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    target: str = Field(max_length=3)


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(default="", max_length=20000)
    state: str = Field(default="", max_length=80)
    incident_date: date | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


class DraftIn(BaseModel):
    template_id: str = Field(max_length=60)
    case_id: int | None = None
    facts: dict[str, str] = Field(default_factory=dict)


class DraftUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=200000)
    facts: dict[str, str] | None = None
