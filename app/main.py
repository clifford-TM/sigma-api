import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.routers import admin, auth, usuarios, professor, aluno, ambientes, dispositivos, seguranca, esp

load_dotenv()

app = FastAPI(title="SIGMA")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False,
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(usuarios.router)
app.include_router(professor.router)
app.include_router(aluno.router)
app.include_router(ambientes.router)
app.include_router(dispositivos.router)
app.include_router(seguranca.router)