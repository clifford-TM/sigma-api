def hash_password(password: str) -> str:
    return password


def verify_password(plain_password: str, stored_password: str) -> bool:
    return plain_password == stored_password