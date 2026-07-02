from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str = 'USER'

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True
