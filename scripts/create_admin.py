import sys
from pathlib import Path
from os import environ
from getpass import getpass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, engine, SessionLocal  # noqa: E402
from app.models.entities import User, Role  # noqa: E402


def main():
    email = environ.get("BOOTSTRAP_ADMIN_EMAIL") or input("Admin email: ").strip()
    password = environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        password = getpass("Admin password (12+ characters): ")
        confirmation = getpass("Confirm admin password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")
    if not email or len(password) < 12:
        raise SystemExit("A valid email and a password of at least 12 characters are required.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That administrator email already exists.")
        db.add(
            User(
                email=email,
                full_name="System Administrator",
                password_hash=hash_password(password),
                role=Role.ADMIN,
            )
        )
        db.commit()
    print(f"Administrator {email} created.")


if __name__ == "__main__":
    main()
