"""Database engine and session management for the auth database."""

from collections.abc import Generator
from contextlib import contextmanager
import os
import threading

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import AuthBase

DEFAULT_AUTH_DSN = "sqlite:////data/auth/auth.db"

_factory: sessionmaker | None = None
_engine: Engine | None = None
_lock = threading.Lock()


def init_auth_db() -> None:
    """Create the authentication tables if they do not exist."""
    AuthBase.metadata.create_all(auth_engine())


@contextmanager
def auth_transaction() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of auth operations."""
    session = get_auth_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth_session() -> Session:
    """Return a new auth database session."""
    return _build()()


def auth_engine() -> Engine:
    """Return the auth database engine, building it on first use."""
    _build()
    assert _engine is not None
    return _engine


def auth_dsn() -> str:
    """Return the configured SQLAlchemy DSN for the auth database."""
    return os.environ.get("AUTH_DSN", DEFAULT_AUTH_DSN)


def reset_engine() -> None:
    """Dispose and reset the cached engine and session factory."""
    global _engine, _factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _factory = None


def _build() -> sessionmaker:
    global _engine, _factory
    with _lock:
        if _factory is None:
            dsn = auth_dsn()
            connect_args = {"check_same_thread": False} if dsn.startswith("sqlite") else {}
            _engine = create_engine(dsn, echo=False, connect_args=connect_args)
            _factory = sessionmaker(bind=_engine, autoflush=True, expire_on_commit=False)
        return _factory
