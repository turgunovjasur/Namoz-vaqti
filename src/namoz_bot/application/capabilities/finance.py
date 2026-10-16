"""Personal ledger capability metadata; execution reuses LedgerService."""

from namoz_bot.application.capabilities.base import operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec

GUIDANCE = """
Summa musbat butun so‘m: 120 ming=120000, bir yarim million=1500000. Valyuta aytilmasa UZS,
boshqa valyuta OTHER; konvertatsiya qilma. Faqat amalga oshgan kirim/chiqimni yoz, kelajakdagi
rejani yozma. category:
oylik,boshqa_kirim,kiyim,oziq_ovqat,transport,uy_joy,sogliq,talim,aloqa,boshqa. Izohni qisqa,
asl ma’noda saqla. Oylik hisobot report_type summary/income/expense/salary; sarfladim=expense.
Oy YYYY-MM; yil xabar sanasidan. Sana/oy aytilmasa tashlab ket: xizmat xabar sanasini oladi.
Summalarni hisoblama. IDni o‘ylab topma; ochiq ID=target_id, nom=text, ikkinchisi=ordinal2;
oxirgi yozuv bo‘lsa nishon bo‘sh. Sahifa 0dan boshlanadi, keyingi=page_step next,
oldingi=previous. Followupda oldingi sana/kategoriya/izohni saqla.
""".strip()


def definitions() -> tuple[CapabilitySpec, ...]:
    return tuple(
        operation(
            f"finance.{action}",
            name,
            description,
            "accounting",
            action,
            effect,
            guidance=GUIDANCE,
            correction_id="finance.correct" if action in {"income", "expense", "correct"} else None,
            requires_result=action == "correct",
        )
        for action, name, description, effect in (
            (
                "correct",
                "Yozuvni tuzatish",
                "Asl yozuvga bog‘lab tasdiqlangan moliyaviy tuzatish.",
                "write",
            ),
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
