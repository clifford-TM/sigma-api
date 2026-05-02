from passlib.context import CryptContext
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def gerar_device_secret() -> str:
    return secrets.token_urlsafe(32)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    return pwd_context.verify(plain_password, stored_password)