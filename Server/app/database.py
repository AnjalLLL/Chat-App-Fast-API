import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("NEON_DATABASE_URL"))
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL or NEON_DATABASE_URL environment variable is required")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret").encode("utf-8")

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(50), unique=True, nullable=False, index=True),
    Column("password_hash", String(256), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("room_id", String(64), nullable=False, index=True),
    Column("user_id", String(50), nullable=False),
    Column("event_type", String(20), nullable=False),
    Column("content", Text, nullable=True),
    Column("timestamp", Integer, nullable=False, index=True),
)

revoked_tokens = Table(
    "revoked_tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("token", Text, unique=True, nullable=False),
    Column("revoked_at", DateTime, nullable=False, default=datetime.utcnow),
)

engine = create_async_engine(DATABASE_URL, future=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return hmac.compare_digest(computed.hex(), digest_hex)


def create_token(username: str, expires_seconds: int = 86_400) -> str:
    expires = int(time.time()) + expires_seconds
    payload = f"{username}:{expires}"
    signature = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload}:{signature}".encode("utf-8")).decode("utf-8").rstrip("=")
    return token


async def is_token_revoked(token: str) -> bool:
    async with async_session() as session:
        query = select(revoked_tokens.c.id).where(revoked_tokens.c.token == token)
        revoked_id = await session.scalar(query)
        return revoked_id is not None


async def verify_token(token: str, username: str) -> bool:
    if await is_token_revoked(token):
        return False
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        token_username, expires, signature = decoded.split(":", 2)
        if token_username != username:
            return False
        if int(expires) < int(time.time()):
            return False
        expected = hmac.new(SECRET_KEY, f"{token_username}:{expires}".encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


async def revoke_token(token: str) -> None:
    async with async_session() as session:
        await session.execute(
            insert(revoked_tokens).values(token=token, revoked_at=datetime.utcnow())
        )
        await session.commit()


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)


async def create_user(username: str, password: str) -> bool:
    async with async_session() as session:
        existing = await session.scalar(select(users.c.id).where(users.c.username == username))
        if existing is not None:
            return False
        password_hash = _hash_password(password)
        await session.execute(
            insert(users).values(username=username, password_hash=password_hash, created_at=datetime.utcnow())
        )
        await session.commit()
        return True


async def authenticate_user(username: str, password: str) -> bool:
    async with async_session() as session:
        query = select(users.c.password_hash).where(users.c.username == username)
        result = await session.execute(query)
        stored_hash = result.scalar_one_or_none()
        if not stored_hash:
            return False
        return _verify_password(password, stored_hash)


async def save_message(room_id: str, user_id: str, event_type: str, content: str | None, timestamp: int) -> None:
    async with async_session() as session:
        await session.execute(
            insert(messages).values(
                room_id=room_id,
                user_id=user_id,
                event_type=event_type,
                content=content,
                timestamp=timestamp,
            )
        )
        await session.commit()


async def get_last_messages(room_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    async with async_session() as session:
        query = (
            select(messages)
            .where(messages.c.room_id == room_id)
            .order_by(messages.c.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.fetchall()
    return [
        {
            "type": row.event_type,
            "user_id": row.user_id,
            "room_id": row.room_id,
            "text": row.content,
            "timestamp": row.timestamp,
        }
        for row in reversed(rows)
    ]
