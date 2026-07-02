import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext

from database import get_connection as get_client_db
from database_users import get_connection as get_user_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "dev_fallback_secret_key_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

app = FastAPI(title="CRM Prototype API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        token = authorization.replace("Bearer ", "")
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def require_role(roles: list):
    def wrapper(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403, 
                detail="You do not have permission to perform this action"
            )
        return user
    return wrapper

class Client(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    company: str

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class Partner(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    company: str

class PartnerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None

@app.post("/login")
def login(data: LoginRequest):
    conn = get_user_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, role FROM users WHERE username=?", (data.username,))
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    user_id, username, hashed_password, role = user
    if not verify_password(data.password, hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_access_token({"user_id": user_id, "username": username, "role": role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user_id, "username": username, "role": role}
    }

@app.get("/clients")
def get_clients(user=Depends(require_role(["admin", "staff", "manager"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, email, phone, company FROM clients")
        rows = cursor.fetchall()
    finally:
        conn.close()
        
    return [
        {"id": r[0], "first_name": r[1], "last_name": r[2], "email": r[3], "phone": r[4], "company": r[5]} 
        for r in rows
    ]

@app.post("/clients")
def create_client(client: Client, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clients (first_name, last_name, email, phone, company) 
            VALUES (?, ?, ?, ?, ?)
        """, (client.first_name, client.last_name, client.email, client.phone, client.company))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Client created successfully"}

@app.patch("/clients/{client_id}")
def update_client_partial(client_id: int, client: ClientUpdate, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, email, phone, company FROM clients WHERE id = ?", (client_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
            
        new_first_name = client.first_name if client.first_name is not None else existing[1]
        new_last_name = client.last_name if client.last_name is not None else existing[2]
        new_email = client.email if client.email is not None else existing[3]
        new_phone = client.phone if client.phone is not None else existing[4]
        new_company = client.company if client.company is not None else existing[5]
        
        cursor.execute("""
            UPDATE clients SET first_name=?, last_name=?, email=?, phone=?, company=? WHERE id=?
        """, (new_first_name, new_last_name, new_email, new_phone, new_company, client_id))
        conn.commit()
    finally:
        conn.close()
        
    return {"message": "Client updated successfully"}

@app.put("/clients/{client_id}")
def update_client(client_id: int, client: Client, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clients SET first_name=?, last_name=?, email=?, phone=?, company=? WHERE id=?
        """, (client.first_name, client.last_name, client.email, client.phone, client.company, client_id))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Client updated successfully"}

@app.delete("/clients/{client_id}")
def delete_client(client_id: int, user=Depends(require_role(["admin"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Client deleted successfully"}

@app.get("/partners")
def get_partners(user=Depends(require_role(["admin", "staff", "manager"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, email, phone, company FROM partners")
        rows = cursor.fetchall()
    finally:
        conn.close()
        
    return [
        {"id": r[0], "first_name": r[1], "last_name": r[2], "email": r[3], "phone": r[4], "company": r[5]} 
        for r in rows
    ]

@app.post("/partners")
def create_partner(partner: Partner, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO partners (first_name, last_name, email, phone, company) 
            VALUES (?, ?, ?, ?, ?)
        """, (partner.first_name, partner.last_name, partner.email, partner.phone, partner.company))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Partner created successfully"}

@app.patch("/partners/{partner_id}")
def update_partner_partial(partner_id: int, partner: PartnerUpdate, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, email, phone, company FROM partners WHERE id = ?", (partner_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Partner not found")
            
        new_first_name = partner.first_name if partner.first_name is not None else existing[1]
        new_last_name = partner.last_name if partner.last_name is not None else existing[2]
        new_email = partner.email if partner.email is not None else existing[3]
        new_phone = partner.phone if partner.phone is not None else existing[4]
        new_company = partner.company if partner.company is not None else existing[5]
        
        cursor.execute("""
            UPDATE partners SET first_name=?, last_name=?, email=?, phone=?, company=? WHERE id=?
        """, (new_first_name, new_last_name, new_email, new_phone, new_company, partner_id))
        conn.commit()
    finally:
        conn.close()
        
    return {"message": "Partner updated successfully"}

@app.put("/partners/{partner_id}")
def update_partner(partner_id: int, partner: Partner, user=Depends(require_role(["admin", "staff"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE partners SET first_name=?, last_name=?, email=?, phone=?, company=? WHERE id=?
        """, (partner.first_name, partner.last_name, partner.email, partner.phone, partner.company, partner_id))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Partner updated successfully"}

@app.delete("/partners/{partner_id}")
def delete_partner(partner_id: int, user=Depends(require_role(["admin"]))):
    conn = get_client_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM partners WHERE id = ?", (partner_id,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Partner deleted successfully"}
