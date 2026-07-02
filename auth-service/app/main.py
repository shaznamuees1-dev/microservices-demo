from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app import models, schemas, auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title='Auth Service')

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
