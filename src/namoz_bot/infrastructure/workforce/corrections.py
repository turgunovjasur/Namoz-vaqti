"""Shared correction receipt handling; amounts and schedules stay in their repositories."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from namoz_bot.domain.workforce.corrections import CorrectionConflict
from namoz_bot.infrastructure.orm import CorrectionAuditRecord


async def existing_correction(
    session: AsyncSession, user_id: int, source_key: str, kind: str, original_id: int
) -> CorrectionAuditRecord | None:
    if not source_key or len(source_key) > 64:
        raise ValueError("Invalid correction source")
    row = await session.scalar(
        select(CorrectionAuditRecord).where(
            CorrectionAuditRecord.user_id == user_id, CorrectionAuditRecord.source_key == source_key
        )
    )
    if row and (row.kind != kind or row.original_id != original_id):
        raise CorrectionConflict("Correction source reused")
    return row


def audit_correction(
    session: AsyncSession,
    *,
    user_id: int,
    source_key: str,
    kind: str,
    original_id: int,
    replacement_id: int,
    before: object,
    after: object,
) -> None:
    session.add(
        CorrectionAuditRecord(
            user_id=user_id,
            source_key=source_key,
            kind=kind,
            original_id=original_id,
            replacement_id=replacement_id,
            before=json.loads(json.dumps(before, default=str)),
            after=json.loads(json.dumps(after, default=str)),
        )
    )
