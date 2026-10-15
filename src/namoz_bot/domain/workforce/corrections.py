"""Corrections refer to an owned, versioned original, never a new unlinked effect."""

from dataclasses import dataclass

from namoz_bot.domain.accounting import AccountingRequest
from namoz_bot.domain.reminders import ReminderSpec


class CorrectionConflict(ValueError):
    """The target changed, was cancelled, or belongs to another account."""


@dataclass(frozen=True)
class FinanceCorrection:
    original_entry_id: int
    expected_record_revision: int
    replacement: AccountingRequest


@dataclass(frozen=True)
class ReminderCorrection:
    original_reminder_id: int
    expected_record_revision: int
    replacement: ReminderSpec
