"""
Authentication logic and CLI for managing users and API tokens.

    python -m auth create-user alice
    python -m auth issue-token uploader alice --days 90
"""

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from engine import auth_transaction, init_auth_db
from models import ApiToken, Session, User

SESSION_TTL = timedelta(days=30)
COOKIE_NAME = "session"

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class AuthError(Exception):
    """A credential that did not verify."""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manage users and API tokens")
    sub = p.add_subparsers(dest="cmd", required=True)

    new = sub.add_parser("create-user")
    new.add_argument("username")

    mint = sub.add_parser("issue-token")
    mint.add_argument("name")
    mint.add_argument("username")
    mint.add_argument("--days", type=int, help="expire after N days; omit to never expire")

    return p.parse_args()


def main() -> None:
    args = parse_args()
    init_auth_db()
    if args.cmd == "create-user":
        password = getpass.getpass("password: ")
        if password != getpass.getpass("repeat: "):
            raise SystemExit("passwords do not match")
        create_user(args.username, password)
        print(f"created {args.username}")
    elif args.cmd == "issue-token":
        ttl = timedelta(days=args.days) if args.days else None
        print(issue_token(args.name, args.username, ttl))


def create_user(username: str, password: str) -> None:
    with auth_transaction() as session:
        if session.scalar(select(User).where(User.username == username)):
            raise SystemExit(f"user {username!r} already exists")
        session.add(User(username=username, password_hash=hash_password(password)))


def issue_token(name: str, username: str, ttl: timedelta | None = None) -> str:
    with auth_transaction() as session:
        user = _by_username(session, username)
        token = secrets.token_urlsafe(32)
        session.add(
            ApiToken(
                name=name,
                token_hash=_digest(token),
                user_id=user.id,
                expires_at=_now() + ttl if ttl else None,
            )
        )
        return token


def login(username: str, password: str) -> str:
    with auth_transaction() as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("invalid username or password")
        token = secrets.token_urlsafe(32)
        session.add(
            Session(
                user_id=user.id,
                token_hash=_digest(token),
                expires_at=_now() + SESSION_TTL,
            )
        )
        return token


def logout(token: str) -> None:
    with auth_transaction() as session:
        row = session.scalar(select(Session).where(Session.token_hash == _digest(token)))
        if row is not None:
            session.delete(row)


def require_user(token: str | None, api_key: str | None) -> User | None:
    with auth_transaction() as session:
        if token:
            user = _session_user(session, token)
            if user is not None:
                return user
        if api_key:
            return _api_key_user(session, api_key)
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${_derive(password, salt)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt, expected = encoded.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    return secrets.compare_digest(_derive(password, bytes.fromhex(salt)), expected)


def _by_username(session: DbSession, username: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise SystemExit(f"no user {username!r}")
    return user


def _session_user(session: DbSession, token: str) -> User | None:
    row = session.scalar(select(Session).where(Session.token_hash == _digest(token)))
    if row is None:
        return None
    if _expired(row.expires_at):
        session.delete(row)
        return None
    return row.user


def _api_key_user(session: DbSession, api_key: str) -> User | None:
    row = session.scalar(select(ApiToken).where(ApiToken.token_hash == _digest(api_key)))
    if row is None or _expired(row.expires_at):
        return None
    row.last_used_at = _now()
    return row.user


def _expired(at: datetime | None) -> bool:
    if at is None:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at <= _now()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _derive(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT).hex()


if __name__ == "__main__":
    main()
