from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey123changeInProd')
ALGORITHM = 'HS256'

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid or expired token')

def require_role(required_role: str):
    def role_checker(payload: dict = Depends(get_current_user)):
        if payload.get('role') != required_role:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return payload
    return role_checker
