from fastapi import Request
from auth.security import get_oauth_id_from_token
from typing import Optional

async def get_current_user_optional(request: Request) -> Optional[str]:
    """
    Looks for a JWT in the 'Authorization' header. 
    If found and valid, returns oauth_id. 
    If missing or invalid, returns None (Guest Mode).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # User is a guest
    
    token = auth_header.split(" ")[1]
    return get_oauth_id_from_token(token)