from pydantic import BaseModel, EmailStr, Field


class LoginForm(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    tipo: str
    email: EmailStr
    senha: str = Field(min_length=6)


class UsuarioOut(BaseModel):
    id_usuario: int
    nome: str
    tipo: str
    email: EmailStr

    class Config:
        from_attributes = True