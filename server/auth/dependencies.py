from fastapi import Request,HTTPException
from auth.security import get_oauth_id_from_token
from typing import Optional


async def get_current_user_optional(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    token = auth_header.split(" ")[1]
    oauth_id = get_oauth_id_from_token(token)

    if oauth_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return oauth_id
