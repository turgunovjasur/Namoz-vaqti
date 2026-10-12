"""Typed errors used across the domain and application layers."""


class NamozBotError(Exception):
    """Base class for expected bot errors."""


class ScheduleValidationError(NamozBotError, ValueError):
    """Raised when prayer schedule data is incomplete or invalid."""


class UnsupportedRegionError(NamozBotError, LookupError):
    """Raised when a region is outside the supported catalog."""


class ExternalServiceError(NamozBotError):
    """Raised when an external provider is unavailable or malformed."""


class ReligiousReminderCooldownError(NamozBotError):
    """Reject repeated manual generations before the user may try again."""

    def __init__(self, remaining_seconds: int) -> None:
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Yangi nasihat olish uchun {remaining_seconds} soniya kuting.")


class ScheduleDateMismatchError(ScheduleValidationError):
    """Raised when a provider returns a schedule for another date."""


class ScheduleRegionMismatchError(ScheduleValidationError):
    """Raised when a provider returns a schedule for another region."""


class SubscriptionNotFoundError(NamozBotError, LookupError):
    """Raised when a Telegram user has not started the bot yet."""


class MessageSendError(NamozBotError):
    """Raised when Telegram cannot deliver a message."""


class RecipientBlockedError(MessageSendError):
    """Raised when a recipient blocked or deactivated the bot."""
