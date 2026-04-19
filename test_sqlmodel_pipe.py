from __future__ import annotations
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

print("Success")
