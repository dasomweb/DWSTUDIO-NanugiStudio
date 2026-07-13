"""DB 세션."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
)


def init_db() -> None:
    from . import models  # noqa: F401  (테이블 등록을 위해 임포트가 필요하다)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
