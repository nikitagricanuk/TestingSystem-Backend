from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ErrorDetails(BaseModel):
    min_delay_seconds: Optional[float] = Field(None, example=5)
    actual_delay_seconds: Optional[float] = Field(None, example=1.2)

class ErrorResponse(BaseModel):
    error: Optional[Dict[str, Any]] = Field(None)