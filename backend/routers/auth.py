"""
CrowdPulse — Auth Router (JWT)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import jwt, bcrypt, uuid

router = APIRouter()
security = HTTPBearer()
SECRET = "crowdpulse-karnataka-secret-2026"
ALGO   = "HS256"
_users: dict = {}

class SignupReq(BaseModel):
    name: str; email: EmailStr; password: str

class LoginReq(BaseModel):
    email: EmailStr; password: str

def _token(uid, email):
    return jwt.encode({"sub": uid, "email": email,
                       "exp": datetime.utcnow() + timedelta(hours=48)}, SECRET, algorithm=ALGO)

def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        d = jwt.decode(creds.credentials, SECRET, algorithms=[ALGO])
    except Exception:
        raise HTTPException(401, "Invalid token")
    u = _users.get(d["sub"])
    if not u: raise HTTPException(401, "User not found")
    return u

@router.post("/signup")
def signup(r: SignupReq):
    if any(u["email"] == r.email for u in _users.values()):
        raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())
    _users[uid] = {"id": uid, "name": r.name, "email": r.email,
                   "pw": bcrypt.hashpw(r.password.encode(), bcrypt.gensalt()).decode()}
    return {"token": _token(uid, r.email), "name": r.name, "email": r.email}

@router.post("/login")
def login(r: LoginReq):
    u = next((u for u in _users.values() if u["email"] == r.email), None)
    if not u or not bcrypt.checkpw(r.password.encode(), u["pw"].encode()):
        raise HTTPException(401, "Invalid credentials")
    return {"token": _token(u["id"], r.email), "name": u["name"], "email": r.email}

@router.get("/me")
def me(u=Depends(get_user)):
    return {k: v for k, v in u.items() if k != "pw"}


@router.post("/logout")
def logout(_u=Depends(get_user)):
    return {"ok": True, "message": "Logged out successfully"}
