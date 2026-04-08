import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth, dashboard, usuarios

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
app.include_router(dashboard.router)
app.include_router(usuarios.router)