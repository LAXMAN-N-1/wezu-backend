from sqlmodel import SQLModel, Field
from typing import Optional

class Translation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    language_code: str = Field(index=True) # en, hi, es
    key: str = Field(index=True) # welcome_message
    value: str # The translated text
    
    context: Optional[str] = None # For specialized context
