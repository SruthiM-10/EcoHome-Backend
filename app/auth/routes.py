# app/auth/routes.py

import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

from app.db.database import get_db
from app.db.schemas import UserCreate as RegisterRequest, UserLogin as LoginRequest
from app.db.models import User
from app.utils.token import create_access_token, create_email_token, decode_token
from app.utils.hashing import hash_password, verify_password
from app.utils.emailer import send_email
from app.auth.security import get_current_user  # We will create this dependency
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Load environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8001")
GOOGLE_REDIRECT_URI = f"{BACKEND_BASE_URL}/auth/google/callback"
REDIRECT_URI = "https://www.google.com"
Project_ID = os.getenv("DEVICE_ACCESS_PROJECT_ID")

# serializer for signing the state token
serializer = URLSafeTimedSerializer(SECRET_KEY)


@router.post("/register")
def register_user(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    password = body.password
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed, is_verified=False)
    db.add(user);
    db.commit();
    db.refresh(user)
    vtok = create_email_token(email)
    verify_link = f"{BACKEND_BASE_URL}/auth/verify?token={vtok}"
    html = f"""<p>Please verify your email by clicking on the link below:</p><p><a href="{verify_link}">Verify Email</a></p>"""
    send_email(to=email, subject="Verify your Thermostat App email", html=html)
    return {"message": "Registration successful. Check your email to verify your account."}


@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(token)
        if payload.get("purpose") != "verify": raise ValueError("Invalid purpose")
        email = payload.get("sub")
        if not email: raise ValueError("Missing subject")
    except Exception:
        raise HTTPException(status_code=400, detail="Link invalid or expired")
    u = db.query(User).filter(User.email == email).first()
    if not u: raise HTTPException(status_code=404, detail="User not found")
    if not u.is_verified:
        u.is_verified = True
        db.commit()
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/login")
# def login_user(body: LoginRequest, db: Session = Depends(get_db)):
#     # ... (This code remains unchanged)
#     email = body.email.strip().lower()
#     password = body.password
#     user = db.query(User).filter(User.email == email).first()
#     if not user or not verify_password(password, user.hashed_password):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     if not user.is_verified:
#         raise HTTPException(status_code=403, detail="Email not verified")
#     access_token = create_access_token({"sub": user.email})
#     return {"access_token": access_token, "token_type": "bearer"}
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.strip().lower()  # <-- CHANGE THIS
    password = form_data.password  # <-- CHANGE THIS

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    access_token = create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- New Google OAuth 2.0 Routes ---

# @router.get("/google/connect", summary="Start Google OAuth2 flow")
# def google_connect(current_user: User = Depends(get_current_user)):
#     """
#     This endpoint starts the Google OAuth2 flow. It should be called by a
#     logged-in user. It creates a secure state token and redirects the user
#     to Google's consent screen.
#     """
#     # Create a state token to prevent CSRF attacks.
#     # We sign the user's email into the token.
#     state = serializer.dumps(current_user.email)

#     # The 'scope' defines what permissions we are asking for.
#     scope = "https://www.googleapis.com/auth/sdm.service"

#     # Construct the authorization URL
#     google_auth_url = (
#         f"https://accounts.google.com/o/oauth2/v2/auth?"
#         f"response_type=code&"
#         f"client_id={GOOGLE_CLIENT_ID}&"
#         f"redirect_uri={GOOGLE_REDIRECT_URI}&"
#         f"scope={scope}&"
#         f"state={state}&"
#         f"access_type=offline&" # Important to get a refresh_token
#         f"prompt=consent"
#     )
#     print("Redirecting user to:", google_auth_url)


#     return RedirectResponse(url=google_auth_url)

# @router.get("/google/connect", summary="Start Google Nest SDM OAuth2 flow")
# def google_connect(current_user: User = Depends(get_current_user)):
#     """
#     Starts the Google Nest Partner Connections OAuth flow (PCM).
#     """
#     state = serializer.dumps(current_user.email)
#     project_id = os.getenv("DEVICE_ACCESS_PROJECT_ID")

#     # SDM scope (required)
#     scope = "https://www.googleapis.com/auth/sdm.service"

#     # ⚠️ IMPORTANT: Use 'nestservices.google.com/partnerconnections'
#     google_auth_url = (
#         f"https://nestservices.google.com/partnerconnections/{project_id}/auth?"
#         f"redirect_uri={REDIRECT_URI}&"
#         f"access_type=offline&"
#         f"prompt=consent&"
#         f"client_id={GOOGLE_CLIENT_ID}&"
#         f"response_type=code&"
#         f"scope={scope}&"
#     )

#     print("Redirecting to:", google_auth_url)
#     return RedirectResponse(url=google_auth_url)
@router.get("/google/connect", summary="Start Google Nest SDM OAuth2 flow")
def google_connect(current_user: User = Depends(get_current_user)):
    """
    Returns a Google Nest OAuth2 authorization URL as JSON
    (React Native cannot follow redirects safely).
    """
    state = serializer.dumps(current_user.email)
    project_id = os.getenv("DEVICE_ACCESS_PROJECT_ID")

    scope = "https://www.googleapis.com/auth/sdm.service"

    google_auth_url = (
        f"https://nestservices.google.com/partnerconnections/{project_id}/auth?"
        f"redirect_uri={REDIRECT_URI}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"response_type=code&"
        f"scope={scope}"
    )

    print("🔗 Google Auth URL:", google_auth_url)

    # ✅ Return JSON instead of redirect
    return JSONResponse({"auth_url": google_auth_url})


@router.post("/google/token", summary="Exchange authorization code for tokens")
async def exchange_google_token(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """
    Step 2: Exchange the authorization code for access/refresh tokens.
    Uses the logged-in user's JWT instead of requiring email.
    """
    body = await request.json()
    code = body.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_url = "https://www.googleapis.com/oauth2/v4/token"
    token_data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "https://www.google.com",  # must match the one used in Google flow
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_data)

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=token_response.status_code,
            detail=f"Failed to fetch tokens: {token_response.text}",
        )

    token_json = token_response.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token returned")

    # Save tokens for this user
    current_user.google_access_token = access_token
    if refresh_token:
        current_user.google_refresh_token = refresh_token
    db.commit()

    return {
        "message": "Tokens retrieved successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.get("/google/callback", summary="Handle Google OAuth2 callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handles the callback from Google. It exchanges the authorization code
    for an access token and refresh token, and saves them for the user.
    """
    code = request.query_params.get('code')
    state = request.query_params.get('state')

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state from Google callback")

    # Verify the state token
    try:
        # The token is valid for 5 minutes
        user_email = serializer.loads(state, max_age=300)
    except (SignatureExpired, BadTimeSignature):
        raise HTTPException(status_code=400, detail="Invalid or expired state token.")

    # Get the user from the database
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User specified in state token not found.")

    # Exchange the authorization code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=token_data)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch token: {response.json()}",
        )

    token_json = response.json()
    google_access_token = token_json.get("access_token")
    google_refresh_token = token_json.get("refresh_token")

    # Save the tokens to the user's record in the database
    user.google_access_token = google_access_token
    # IMPORTANT: The refresh token is only sent the first time the user authorizes.
    # Only update it if a new one is provided.
    if google_refresh_token:
        user.google_refresh_token = google_refresh_token

    db.commit()

    return {"message": "Google account linked successfully!"}


@router.get("/google/devices", summary="Get user's Nest devices")
async def get_google_devices(current_user: User = Depends(get_current_user)):
    """
    Step 3: Call Google SDM API using the stored access token.
    """
    project_id = os.getenv("DEVICE_ACCESS_PROJECT_ID")
    access_token = current_user.google_access_token

    if not access_token:
        raise HTTPException(status_code=400, detail="User has no linked Google access token")

    devices_url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{project_id}/devices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        devices_response = await client.get(devices_url, headers=headers)

    if devices_response.status_code != 200:
        raise HTTPException(
            status_code=devices_response.status_code,
            detail=f"Device list fetch failed: {devices_response.text}",
        )

    devices_data = devices_response.json()
    print("✅ Devices linked:", devices_data)

    return {"devices": devices_data}


@router.post("/google/refresh", summary="Refresh Google access token")
async def refresh_google_token(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    refresh_token = current_user.google_refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token stored")

    token_url = "https://www.googleapis.com/oauth2/v4/token"
    token_data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=token_data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    token_json = response.json()
    new_access_token = token_json.get("access_token")

    # Save new access token to DB
    current_user.google_access_token = new_access_token
    db.commit()

    return {"access_token": new_access_token}

# import os
# import httpx
# from fastapi import APIRouter, Depends, HTTPException, status, Request
# from fastapi.responses import RedirectResponse
# from sqlalchemy.orm import Session
# from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

# from app.db.database import get_db
# from app.db.schemas import UserCreate as RegisterRequest, UserLogin as LoginRequest
# from app.db.models import User
# from app.utils.token import create_access_token, create_email_token, decode_token
# from app.utils.hashing import hash_password, verify_password
# from app.utils.emailer import send_email
# from app.auth.security import get_current_user # We will create this dependency
# from fastapi.security import OAuth2PasswordRequestForm

# router = APIRouter(prefix="/auth", tags=["auth"])

# # Load environment variables
# SECRET_KEY = os.getenv("SECRET_KEY")
# GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8001")
# PUBLIC_URL = os.getenv("PUBLIC_URL", "https://dev.sustainable-house.com")
# GOOGLE_REDIRECT_URI = f"{PUBLIC_URL}/auth/google/callback"

# # serializer for signing the state token
# serializer = URLSafeTimedSerializer(SECRET_KEY)


# @router.post("/register")
# def register_user(body: RegisterRequest, db: Session = Depends(get_db)):
#     email = body.email.strip().lower()
#     password = body.password
#     existing = db.query(User).filter(User.email == email).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")
#     hashed = hash_password(password)
#     user = User(email=email, hashed_password=hashed, is_verified=False)
#     db.add(user); db.commit(); db.refresh(user)
#     vtok = create_email_token(email)
#     verify_link = f"{BACKEND_BASE_URL}/auth/verify?token={vtok}"
#     html = f"""<p>Please verify your email by clicking on the link below:</p><p><a href="{verify_link}">Verify Email</a></p>"""
#     send_email(to=email, subject="Verify your Thermostat App email", html=html)
#     return {"message": "Registration successful. Check your email to verify your account."}

# @router.get("/verify")
# def verify_email(token: str, db: Session = Depends(get_db)):
#     try:
#         payload = decode_token(token)
#         if payload.get("purpose") != "verify": raise ValueError("Invalid purpose")
#         email = payload.get("sub")
#         if not email: raise ValueError("Missing subject")
#     except Exception:
#         raise HTTPException(status_code=400, detail="Link invalid or expired")
#     u = db.query(User).filter(User.email == email).first()
#     if not u: raise HTTPException(status_code=404, detail="User not found")
#     if not u.is_verified:
#         u.is_verified = True
#         db.commit()
#     return {"message": "Email verified successfully. You can now log in."}

# @router.post("/login")
# # def login_user(body: LoginRequest, db: Session = Depends(get_db)):
# #     # ... (This code remains unchanged)
# #     email = body.email.strip().lower()
# #     password = body.password
# #     user = db.query(User).filter(User.email == email).first()
# #     if not user or not verify_password(password, user.hashed_password):
# #         raise HTTPException(status_code=401, detail="Invalid credentials")
# #     if not user.is_verified:
# #         raise HTTPException(status_code=403, detail="Email not verified")
# #     access_token = create_access_token({"sub": user.email})
# #     return {"access_token": access_token, "token_type": "bearer"}
# def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
#     email = form_data.username.strip().lower() # <-- CHANGE THIS
#     password = form_data.password             # <-- CHANGE THIS

#     user = db.query(User).filter(User.email == email).first()
#     if not user or not verify_password(password, user.hashed_password):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     if not user.is_verified:
#         raise HTTPException(status_code=403, detail="Email not verified")

#     access_token = create_access_token({"sub": user.email})
#     return {"access_token": access_token, "token_type": "bearer"}


# # --- New Google OAuth 2.0 Routes ---

# @router.get("/google/connect", summary="Start Google OAuth2 flow")
# def google_connect(current_user: User = Depends(get_current_user)):
#     """
#     This endpoint starts the Google OAuth2 flow. It should be called by a
#     logged-in user. It creates a secure state token and redirects the user
#     to Google's consent screen.
#     """
#     # Create a state token to prevent CSRF attacks.
#     # We sign the user's email into the token.
#     print("Started 1")
#     state = serializer.dumps(current_user.email)

#     print("Started 2")
#     # The 'scope' defines what permissions we are asking for.
#     scope = "https://www.googleapis.com/auth/sdm.service"

#     # Construct the authorization URL
#     google_auth_url = (
#         f"https://accounts.google.com/o/oauth2/v2/auth?"
#         f"response_type=code&"
#         f"client_id={GOOGLE_CLIENT_ID}&"
#         f"redirect_uri={GOOGLE_REDIRECT_URI}&"
#         f"scope={scope}&"
#         f"state={state}&"
#         f"access_type=offline&" # Important to get a refresh_token
#         f"prompt=consent"
#     )

#     return RedirectResponse(url=google_auth_url)


# @router.get("/google/callback", summary="Handle Google OAuth2 callback")
# async def google_callback(request: Request, db: Session = Depends(get_db)):
#     """
#     Handles the callback from Google. It exchanges the authorization code
#     for an access token and refresh token, and saves them for the user.
#     """

#     print("Started 3")
#     code = request.query_params.get('code')
#     state = request.query_params.get('state')

#     if not code or not state:
#         raise HTTPException(status_code=400, detail="Missing code or state from Google callback")

#     print("Started 4")
#     # Verify the state token
#     try:
#         # The token is valid for 5 minutes
#         user_email = serializer.loads(state, max_age=300)
#     except (SignatureExpired, BadTimeSignature):
#         raise HTTPException(status_code=400, detail="Invalid or expired state token.")

#     print("Started 5")
#     # Get the user from the database
#     user = db.query(User).filter(User.email == user_email).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User specified in state token not found.")

#     print("Started 6")
#     # Exchange the authorization code for tokens
#     token_url = "https://oauth2.googleapis.com/token"
#     token_data = {
#         "code": code,
#         "client_id": GOOGLE_CLIENT_ID,
#         "client_secret": GOOGLE_CLIENT_SECRET,
#         "redirect_uri": GOOGLE_REDIRECT_URI,
#         "grant_type": "authorization_code",
#     }

#     async with httpx.AsyncClient() as client:
#         response = await client.post(token_url, data=token_data)

#     print("Started 7")

#     if response.status_code != 200:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Failed to fetch token: {response.json()}",
#         )

#     print("Started 8")

#     token_json = response.json()
#     google_access_token = token_json.get("access_token")
#     google_refresh_token = token_json.get("refresh_token")

#     print("Started 9")

#     # Save the tokens to the user's record in the database
#     user.google_access_token = google_access_token
#     # IMPORTANT: The refresh token is only sent the first time the user authorizes.
#     # Only update it if a new one is provided.
#     if google_refresh_token:
#         user.google_refresh_token = google_refresh_token

#     print("Started 10")

#     db.commit()

#     return {"message": "Google account linked successfully!"}


# simple authentication

# # app/auth/routes.py
# from fastapi import APIRouter, Depends, HTTPException, Response
# from sqlalchemy.orm import Session
# from app.db.database import get_db
# # from app.utils import hashing, token
# from app.utils.emailer import send_email
# # from .schemas import RegisterRequest, LoginRequest
# from app.db.schemas import UserCreate as RegisterRequest, UserLogin as LoginRequest
# from app.db.models import User
# import os

# from app.utils.token import create_access_token, create_email_token, decode_token
# from app.utils.hashing import hash_password, verify_password

# router = APIRouter(prefix="/auth", tags=["auth"])
# BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8001")

# @router.post("/register")
# def register_user(body: RegisterRequest, db: Session = Depends(get_db)):
#     email = body.email.strip().lower()
#     password = body.password

#     existing = db.query(User).filter(User.email == email).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")

#     hashed = hash_password(password)
#     user = User(email=email, hashed_password=hashed, is_verified=False)
#     db.add(user); db.commit(); db.refresh(user)

#     vtok = create_email_token(email)
#     verify_link = f"{BACKEND_BASE_URL}/auth/verify?token={vtok}"

#     html = f"""
#       <div style="font-family:sans-serif">
#         <h2>Verify your email</h2>
#         <p><a href="{verify_link}" style="padding:10px 14px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px">Verify Email</a></p>
#         <p>If the button doesn’t work, paste this link:<br>{verify_link}</p>
#       </div>
#     """
#     send_email(to=email, subject="Verify your Thermostat App email", html=html)
#     return {"message": "Registration successful. Check your email to verify your account."}

# @router.get("/verify")
# def verify_email(token: str, db: Session = Depends(get_db)):
#     try:
#         payload = decode_token(token)
#         if payload.get("purpose") != "verify":
#             raise ValueError("Invalid purpose")
#         email = payload.get("sub")
#         if not email:
#             raise ValueError("Missing subject")
#     except Exception:
#         return Response(
#             "<h2>Verification failed</h2><p>Link invalid or expired.</p>",
#             media_type="text/html", status_code=400
#         )

#     u = db.query(User).filter(User.email == email).first()
#     if not u:
#         return Response("<h2>User not found</h2>", media_type="text/html", status_code=404)

#     if not u.is_verified:
#         u.is_verified = True
#         db.commit()

#     return Response(
#         "<h2>Email verified successfully ✅</h2><p>You can now log in.</p>",
#         media_type="text/html"
#     )

# @router.post("/login")
# def login_user(body: LoginRequest, db: Session = Depends(get_db)):
#     email = body.email.strip().lower()
#     password = body.password

#     user = db.query(User).filter(User.email == email).first()
#     if not user or not verify_password(password, user.hashed_password):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     if not user.is_verified:
#         raise HTTPException(status_code=403, detail="Email not verified")

#     access_token = create_access_token({"sub": user.email})
#     return {"access_token": access_token, "token_type": "bearer"}

