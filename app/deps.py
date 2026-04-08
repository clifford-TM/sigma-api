from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Usuario


def get_current_user(request: Request) -> Usuario:
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Não autenticado",
            headers={"Location": "/login"},
        )

    db: Session = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
        if not user:
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Sessão inválida",
                headers={"Location": "/login"},
            )
        return user
    finally:
        db.close()