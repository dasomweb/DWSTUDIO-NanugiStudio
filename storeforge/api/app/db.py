"""DB 세션.

로컬은 SQLite, 프로덕션(Railway)은 Postgres.
Postgres 연결은 재배포·유휴 후 끊긴 커넥션을 물고 있는 경우가 있어 pre_ping 으로 걸러낸다.
"""

from __future__ import annotations

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


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
