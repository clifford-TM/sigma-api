import secrets
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Dispositivo
from app.security import hash_password  # ← corrigido


DEVICE_ID = "esp32_sala_01"


def gerar_device_secret() -> str:
    return secrets.token_urlsafe(32)


def main():
    db: Session = SessionLocal()

    try:
        dispositivo = (
            db.query(Dispositivo)
            .filter(Dispositivo.identificador_fisico == DEVICE_ID)
            .first()
        )

        if not dispositivo:
            print(f"Dispositivo não encontrado: {DEVICE_ID}")
            return

        novo_secret = gerar_device_secret()

        dispositivo.secret_hash = hash_password(novo_secret)
        dispositivo.ativo = True

        db.commit()

        print("\n✅ SECRET GERADO COM SUCESSO")
        print("-----------------------------")
        print(f"DEVICE_ID: {DEVICE_ID}")
        print(f"SECRET: {novo_secret}")
        print("\n👉 Use esse SECRET no curl ou no ESP")
        print("👉 O banco recebeu apenas o hash\n")

    except Exception as e:
        db.rollback()
        print("❌ Erro ao atualizar secret:")
        print(e)

    finally:
        db.close()


if __name__ == "__main__":
    main()