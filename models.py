"""SQLAlchemy models for authentication (users, sessions, API tokens)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AuthBase(DeclarativeBase):
    pass


class User(AuthBase):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_user_username"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} {self.username}>"


class Session(AuthBase):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_session_token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<Session id={self.id} user={self.user_id}>"


class ApiToken(AuthBase):
    __tablename__ = "api_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_api_token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<ApiToken id={self.id} {self.name} user={self.user_id}>"
