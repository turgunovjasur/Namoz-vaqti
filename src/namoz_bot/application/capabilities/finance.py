"""Personal ledger capability metadata; execution reuses LedgerService."""

from namoz_bot.application.capabilities.base import operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec


def definitions() -> tuple[CapabilitySpec, ...]:
    return tuple(
        operation(f"finance.{action}", name, description, "accounting", action, effect)
        for action, name, description, effect in (
            ("income", "Kirim yozish", "Amalga oshgan kirimni hisobga yozish.", "write"),
            ("expense", "Xarajat yozish", "Amalga oshgan xarajatni hisobga yozish.", "write"),
            ("balance", "Balans", "Shaxsiy hisobning joriy balansini ko‘rish.", "read"),
            ("report", "Hisobot", "Oylik kirim va xarajatlar hisobotini olish.", "read"),
            ("history", "Yozuvlar tarixi", "Shaxsiy moliyaviy yozuvlar tarixini ko‘rish.", "read"),
            (
                "undo",
                "Yozuvni bekor qilish",
                "Tasdiqlangan moliyaviy yozuvni bekor qilish.",
                "write",
            ),
        )
    )
