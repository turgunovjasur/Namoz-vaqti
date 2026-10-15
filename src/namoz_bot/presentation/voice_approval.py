"""Human-readable interpretations; execution identities stay in callback payloads."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.presentation.result_messages import interpretation_text as interpretation_text


def approval_buttons(output: AgentResult) -> InlineKeyboardMarkup:
    prefix = "vr" if output.data.get("voice_review") else "ag"
    token = f"{prefix}:{output.operation_id}:{output.data['revision']}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"{token}:y"),
                InlineKeyboardButton(text="❌ Yo‘q", callback_data=f"{token}:n"),
            ]
        ]
    )
