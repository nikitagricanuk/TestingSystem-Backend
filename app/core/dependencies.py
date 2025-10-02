from typing import Optional
from fastapi import Header, HTTPException

async def get_token_header(x_token: Optional[str] = Header(default=None)):
    # Placeholder dependency to demonstrate structure.
    # Replace with real auth/logic as needed.
    if x_token == "invalid":
        raise HTTPException(status_code=400, detail="Invalid X-Token header")