from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app import models, schemas, auth
import secrets
import time

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title='Auth Service')

# Temporary in-memory store for authorization codes
# In production: use Redis with TTL
auth_codes = {}

@app.get('/')
def health():
    return {'status': 'auth-service running'}

@app.post('/register', response_model=schemas.UserResponse, status_code=201)
def register(user: schemas.UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')
    new_user = models.User(
        email=user.email,
        password_hash=auth.hash_password(user.password),
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post('/login', response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = auth.create_access_token({
        'sub': str(user.id),
        'email': user.email,
        'role': user.role
    })
    return {'access_token': token, 'token_type': 'bearer'}

# -------------- OAuth2 Authorization Code Flow -------------
@app.get('/oauth2/authorize')
def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str = 'openid',
    email: str = None,
    password: str = None,
    db: Session = Depends(get_db)
):
    if response_type != 'code':
        raise HTTPException(status_code=400, detail='Only response_type=code supported')

    # If credentials not provided, return a simple login prompt
    if not email or not password:
        return JSONResponse({
            'message': 'Please provide email and password as query params to simulate login',
            'example': f'/oauth2/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&email=test@test.com&password=password123'
        })

    # Verify credentials
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    # Generate a short-lived authorization code (expires in 60 seconds)
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'scope': scope,
        'expires_at': time.time() + 60
    }

    return RedirectResponse(url=f'{redirect_uri}?code={code}')

@app.post('/oauth2/token')
def token(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(None),
    refresh_token: str = Form(None),
    db: Session = Depends(get_db)
):
    if grant_type == 'authorization_code':
        if not code or code not in auth_codes:
            raise HTTPException(status_code=400, detail='Invalid or expired code')

        code_data = auth_codes.pop(code)  # Single use — remove immediately

        if time.time() > code_data['expires_at']:
            raise HTTPException(status_code=400, detail='Code expired')

        if code_data['redirect_uri'] != redirect_uri:
            raise HTTPException(status_code=400, detail='redirect_uri mismatch')

        user_id = code_data['user_id']
        email = code_data['email']
        role = code_data['role']
        scope = code_data['scope']

    elif grant_type == 'refresh_token':
        if not refresh_token:
            raise HTTPException(status_code=400, detail='refresh_token required')
        try:
            payload = auth.decode_token(refresh_token)
            user_id = payload['sub']
            email = payload['email']
            role = payload['role']
            scope = 'openid'
        except Exception:
            raise HTTPException(status_code=401, detail='Invalid refresh token')
    else:
        raise HTTPException(status_code=400, detail='Unsupported grant_type')

    # Issue access token
    access_token = auth.create_access_token({
        'sub': str(user_id),
        'email': email,
        'role': role
    })

    # Issue refresh token (longer lived)
    new_refresh_token = auth.create_refresh_token({
        'sub': str(user_id),
        'email': email,
        'role': role
    })

    response = {
        'access_token': access_token,
        'token_type': 'bearer',
        'refresh_token': new_refresh_token,
        'expires_in': 1800
    }

    # If openid scope, add id_token (OIDC)
    if 'openid' in scope:
        id_token = auth.create_access_token({
            'sub': str(user_id),
            'email': email,
            'role': role,
            'iss': 'auth-service',
            'aud': client_id or 'client'
        })
        response['id_token'] = id_token

    return response

@app.get('/userinfo')
def userinfo(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')

    token = auth_header.split(' ')[1]
    try:
        payload = auth.decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid token')

    return {
        'sub': payload['sub'],
        'email': payload['email'],
        'role': payload['role']
    }