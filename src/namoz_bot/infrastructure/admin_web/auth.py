"""One-use login tickets and revocable opaque sessions. No credentials in URLs/logs."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.infrastructure.orm import AdminLoginTicketRecord, AdminWebSessionRecord, UserRecord


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hmac.new(token.encode(), b"yordamchi-admin-csrf", hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class AdminIdentity:
    user_id: int
    telegram_user_id: int
    csrf_token: str


class AdminAuth:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], admin_telegram_ids: frozenset[int]
    ) -> None:
        self.factory, self.admin_telegram_ids = factory, admin_telegram_ids

    async def issue_ticket(self, telegram_id: int, *, now: datetime | None = None) -> str:
        if telegram_id not in self.admin_telegram_ids:
            raise AccessDenied("Administrator required")
        now = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        async with self.factory.begin() as session:
            user_id = await session.scalar(
                select(UserRecord.id).where(UserRecord.telegram_user_id == telegram_id)
            )
            if user_id is None:
                raise AccessDenied("Avval botga /start yuboring.")
            await session.execute(
                delete(AdminLoginTicketRecord).where(AdminLoginTicketRecord.expires_at <= now)
            )
            await session.execute(
                delete(AdminWebSessionRecord).where(AdminWebSessionRecord.expires_at <= now)
            )
            session.add(
                AdminLoginTicketRecord(
                    token_hash=digest(token), user_id=user_id, expires_at=now + timedelta(minutes=5)
                )
            )
        return token

    async def exchange_ticket(self, token: str) -> str:
        if not 20 <= len(token) <= 128:
            raise AccessDenied("Kirish havolasi yaroqsiz yoki muddati tugagan.")
        now = datetime.now(UTC)
        session_token = secrets.token_urlsafe(32)
        async with self.factory.begin() as session:
            user_id = await session.scalar(
                delete(AdminLoginTicketRecord)
                .where(
                    AdminLoginTicketRecord.token_hash == digest(token),
                    AdminLoginTicketRecord.expires_at > now,
                )
                .returning(AdminLoginTicketRecord.user_id)
            )
            user = await session.get(UserRecord, user_id) if user_id is not None else None
            if user is None or user.telegram_user_id not in self.admin_telegram_ids:
                raise AccessDenied("Kirish havolasi yaroqsiz yoki muddati tugagan.")
            session.add(
                AdminWebSessionRecord(
                    token_hash=digest(session_token),
                    user_id=user.id,
                    expires_at=now + timedelta(hours=8),
                )
            )
        return session_token

    async def authenticate(self, token: str | None) -> AdminIdentity:
        if token is None or not 20 <= len(token) <= 128:
            raise AccessDenied("Kirish talab qilinadi.")
        async with self.factory() as session:
            user = await session.scalar(
                select(UserRecord)
                .join(AdminWebSessionRecord, AdminWebSessionRecord.user_id == UserRecord.id)
                .where(
                    AdminWebSessionRecord.token_hash == digest(token),
                    AdminWebSessionRecord.expires_at > datetime.now(UTC),
                )
            )
            if user is None or user.telegram_user_id not in self.admin_telegram_ids:
                raise AccessDenied("Kirish muddati tugagan. Botdan yangi havola oling.")
            return AdminIdentity(user.id, user.telegram_user_id, csrf_token(token))

    async def revoke(self, token: str) -> None:
        async with self.factory.begin() as session:
            await session.execute(
                delete(AdminWebSessionRecord).where(
                    AdminWebSessionRecord.token_hash == digest(token)
                )
            )
