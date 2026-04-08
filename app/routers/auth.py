from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.security import verify_password

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="public")


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        user_tipo = request.session.get("user_tipo")

        if user_tipo == "professor":
            destino = "/professor/dashboard"
        elif user_tipo == "aluno":
            destino = "/aluno/dashboard"
        elif user_tipo == "seguranca":
            destino = "/seguranca/dashboard"
        elif user_tipo == "admin":
            destino = "/admin"

        return RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"erro": None},
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(Usuario.email == email).first()

    if not user or not verify_password(senha, user.senha):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"erro": "Email ou senha inválidos."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session["user_id"] = user.id_usuario
    request.session["user_nome"] = user.nome
    request.session["user_tipo"] = user.tipo

    if user.tipo == "professor":
        destino = "/professor/dashboard"
    elif user.tipo == "aluno":
        destino = "/aluno/dashboard"
    elif user.tipo == "seguranca":
        destino = "/seguranca/dashboard"
    elif user.tipo == "admin":
        destino = '/admin'
    return RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)