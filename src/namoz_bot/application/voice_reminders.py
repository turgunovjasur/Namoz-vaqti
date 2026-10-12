"""Bound voice extraction work and repeated requests without writing reminders."""

import asyncio
from datetime import datetime
from time import monotonic
from typing import Protocol

from namoz_bot.domain.voice_reminders import VoiceReminderDraft

MAX_VOICE_BYTES = 5 * 1024 * 1024
MAX_VOICE_SECONDS = 120


class VoiceReminderExtractor(Protocol):
    async def extract(
        self, audio: bytes, *, mime_type: str, now: datetime
    ) -> VoiceReminderDraft: ...


class VoiceReminderService:
    def __init__(self, extractor: VoiceReminderExtractor, *, cooldown_seconds: int = 20) -> None:
        self._extractor = extractor
        self._cooldown = cooldown_seconds
        self._requests: dict[int, float] = {}
        self._slots = asyncio.Semaphore(3)

    async def extract(
        self, user_id: int, audio: bytes, *, mime_type: str, now: datetime
    ) -> VoiceReminderDraft:
        if not audio or len(audio) > MAX_VOICE_BYTES:
            raise ValueError("Iltimos, 5 MB dan kichik qisqa ovozli xabar yuboring.")
        current = monotonic()
        self._requests = {user: until for user, until in self._requests.items() if until > current}
        until = self._requests.get(user_id, 0)
        if until > current:
            raise ValueError(f"Yangi ovozli xabar uchun {int(until - current) + 1} soniya kuting.")
        self._requests[user_id] = current + self._cooldown
        try:
            async with self._slots:
                return await self._extractor.extract(audio, mime_type=mime_type, now=now)
        except Exception:
            self._requests.pop(user_id, None)
            raise
