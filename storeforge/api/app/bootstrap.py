"""최초 부팅 시 슈퍼어드민 1명 생성.

Railway 컨테이너에 셸로 들어가 seed 를 돌리기 번거로우므로 기동 시점에 처리한다.

안전 규칙:
  - 사용자가 이미 한 명이라도 있으면 아무것도 하지 않는다 (기존 계정을 덮어쓰지 않는다)
  - 환경변수가 없으면 조용히 건너뛴다
  - 비밀번호는 로그에 절대 남기지 않는다
"""

from __future__ import annotations

import logging
import os

from sqlmodel import Session, select

from .db import engine
from .models import Role, User
from .security import hash_password

logger = logging.getLogger(__name__)


def bootstrap_superadmin() -> None:
    email = os.getenv("STOREFORGE_BOOTSTRAP_EMAIL", "").strip()
    password = os.getenv("STOREFORGE_BOOTSTRAP_PASSWORD", "").strip()

    if not email or not password:
        return

    if len(password) < 8:
        logger.warning("부트스트랩 비밀번호가 8자 미만입니다. 슈퍼어드민 생성을 건너뜁니다.")
        return

    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            # 사용자가 이미 있다. 기존 계정을 건드리지 않는다.
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
        logger.info("슈퍼어드민을 생성했습니다: %s (첫 로그인 후 비밀번호를 변경하세요)", email)
