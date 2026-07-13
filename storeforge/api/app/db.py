"""DB 세션.

로컬은 SQLite, 프로덕션(Railway)은 Postgres.
Postgres 연결은 재배포·유휴 후 끊긴 커넥션을 물고 있는 경우가 있어 pre_ping 으로 걸러낸다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")

engine = create_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=not _is_sqlite,  # 죽은 커넥션을 재사용하지 않는다
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


def init_db() -> None:
    from . import models  # noqa: F401  (테이블 등록을 위해 임포트가 필요하다)

    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """가벼운 전진 마이그레이션.

    create_all 은 없는 테이블만 만들고 기존 테이블에 컬럼을 추가하지는 않는다.
    Alembic 을 붙이기 전까지는 여기서 멱등한 ALTER 를 돌린다.
    (아직 스토어가 0건인 초기 단계라 이 정도로 충분하다. 데이터가 쌓이면 Alembic 으로 옮길 것.)
    """
    from sqlalchemy import text

    if _is_sqlite:
        return  # 로컬은 DB 파일을 지우고 다시 만들면 된다

    stmts = [
        # client_credentials 방식 지원 (스토어별 자격증명)
        "ALTER TABLE store ADD COLUMN IF NOT EXISTS auth_type VARCHAR DEFAULT 'client_credentials'",
        "ALTER TABLE store ADD COLUMN IF NOT EXISTS encrypted_client_id VARCHAR",
        "ALTER TABLE store ADD COLUMN IF NOT EXISTS encrypted_client_secret VARCHAR",
        "ALTER TABLE store ADD COLUMN IF NOT EXISTS granted_scopes VARCHAR",
        # token 방식은 이제 선택이다 (client_credentials 를 쓰면 비어 있다)
        "ALTER TABLE store ALTER COLUMN encrypted_token DROP NOT NULL",
        # 통합 앱 — 스토어마다 켠 모듈이 다르다 (capabilities.py)
        "ALTER TABLE store ADD COLUMN IF NOT EXISTS enabled_modules VARCHAR DEFAULT 'storeforge'",
        "UPDATE store SET enabled_modules = 'storeforge' WHERE enabled_modules IS NULL",
    ]

    with engine.begin() as conn:
        for sql in stmts:
            try:
                conn.execute(text(sql))
            except Exception as exc:  # noqa: BLE001 — 이미 적용된 마이그레이션은 무시
                logging.getLogger(__name__).debug("마이그레이션 건너뜀: %s (%s)", sql, exc)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
