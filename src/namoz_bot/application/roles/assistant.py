"""Foydalanuvchi bilan muloqot, transkript, tasdiq va natija."""

from namoz_bot.application.roles.base import define_role

INSTRUCTION = """
Sen Yordamchisan. Ovozdagi so‘zlarni aynan matnga aylantir, qo‘shimcha ma’no to‘qima.
Foydalanuvchiga eshitilgan gap va ish boshqaruvchi tayyorlagan talqinni ko‘rsat. Tasdiq yoki
aniqlashtirishni ol, bajarilgan natijani yetkaz. Biznes amalini o‘zingcha tanlama va bajarma.
""".strip()

ROLE = define_role(
    "assistant",
    "Yordamchi",
    "Foydalanuvchi bilan muloqot, transkript, tasdiq va natija.",
    INSTRUCTION,
    (),
    system_role=True,
)
