"""초기 superadmin 생성.

    python seed.py [email] [password]
"""

from __future__ import annotations

import sys

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Role, User
from app.security import hash_password


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "dasomweb@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "storeforge!2026"

    init_db()
    with Session(engine) as session:
        if session.exec(select(User).where(User.email == email)).first():
            print(f"이미 존재: {email}")
            return

        session.add(
            User(
                email=email,
                name="DASOMWEB",
                password_hash=hash_password(password),
                role=Role.superadmin,
            )
        )
        session.commit()
        print(f"superadmin 생성 완료: {email}")
        print("첫 로그인 후 비밀번호를 반드시 변경하세요.")


if __name__ == "__main__":
    main()
