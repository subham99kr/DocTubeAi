import os
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from global_modules.pg_pool import get_pg_pool
from auth.security import create_secure_jwt
from global_modules.http_client import get_http_client
from logger import logger

router = APIRouter(tags=["Auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

@router.get("/login/google")
async def login_google():
    """Step 1: Redirect user to Google Login Page."""
    url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"response_type=code&client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"scope=openid%20profile%20email&access_type=offline"
    )
    return RedirectResponse(url=url)

@router.get("/auth/callback")
async def auth_callback(code: str):
    """Step 2: Exchange Google Code for a Secure Internal JWT."""
    try:
        client = await get_http_client()
        # 1. Trade authorization code for access token
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_res.raise_for_status()
        google_tokens = token_res.json()

        # 2. Use access token to get user's profile info
        user_info_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"}
        )
        user_info_res.raise_for_status()
        user_data = user_info_res.json()
        
        # 3. Extract relevant data
        oauth_id = user_data.get("sub")  # Google's unique ID
        email = user_data.get("email")
        name = user_data.get("name")

        if not oauth_id:
            raise ValueError("Google did not provide a unique ID (sub).")

        # 4. Save/Update user in Postgres
        await upsert_user(oauth_id, email, name)

        # 5. GENERATE YOUR SECURE JWT
        # We encrypt the oauth_id inside this token
        access_token = create_secure_jwt(oauth_id)

        # 6. Return the Secure Token to your Frontend
        return JSONResponse(content={
            "status": "success",
            "access_token": access_token,  # this is the gibberish token
            "token_type": "bearer",
            "user": {
                "email": email,
                "name": name
            }
        })

    except Exception as e:
        logger.exception(f"🔴 Auth Callback failed: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed. Please try again.")

async def upsert_user(oauth_id: str, email: str, name: str):
    """Ensures the user exists in our DB and updates their name if changed."""
    pool = await get_pg_pool()
    query = """
        INSERT INTO users (oauth_id, email, full_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (oauth_id) DO UPDATE 
        SET full_name = EXCLUDED.full_name,
            last_login = NOW();
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (oauth_id, email, name))
        await conn.commit()