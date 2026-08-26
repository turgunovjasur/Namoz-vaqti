"""Typed errors used across the domain and application layers."""


class NamozBotError(Exception):
    """Base class for expected bot errors."""


class ScheduleValidationError(NamozBotError, ValueError):
    """Raised when prayer schedule data is incomplete or invalid."""


class UnsupportedRegionError(NamozBotError, LookupError):
    """Raised when a region is outside the supported catalog."""


class ExternalServiceError(NamozBotError):
    """Raised when an external provider is unavailable or malformed."""


class ScheduleDateMismatchError(ScheduleValidationError):
    """Raised when a provider returns a schedule for another date."""


class ScheduleRegionMismatchError(ScheduleValidationError):
    """Raised when a provider returns a schedule for another region."""
