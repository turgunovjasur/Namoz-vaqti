from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.presentation.result_messages import render_interpretation, render_result


def output(domain, action, data):
    return AgentResult(
        request_id="request",
        operation_id="operation",
        domain=domain,
        action=action,
        status="done",
        data=data,
    )


def test_accounting_renderers_preserve_saved_amount_and_actual_balance():
    result = output(
        "accounting",
        "expense",
        {
            "entry_id": 17,
            "amount": 120000,
            "description": "Kiyim",
            "balance": 880000,
        },
    )
    for legacy in (False, True):
        text = render_result(result, legacy=legacy)
        assert "120 000" in text and "880 000" in text and "Kiyim" in text
    assert "Chiqim qayd" in render_result(result, legacy=True)
    assert "saqlandi" in render_result(result)


def test_prayer_and_nasihat_keep_authoritative_source_facts():
    prayer = output(
        "prayer",
        "schedule",
        {
            "prayer": "shom",
            "time": "18:05",
            "date": "2026-10-15",
            "region": "Toshkent",
        },
    )
    for legacy in (False, True):
        text = render_result(prayer, legacy=legacy)
        assert "Shom: 18:05" in text and "namoz-vaqti.uz" in text
    quotation = "Kitobdagi asl parcha.\nManba: Sinov kitobi, 12-bet."
    assert render_result(output("nasihat", "religious_excerpt", {"text": quotation})) == quotation


def test_interpretation_uses_registered_capability_and_original_transcript():
    text = render_interpretation(
        "120 mingga kiyim oldim",
        CapabilitySelection(
            role_id="accounting",
            capability_id="finance.expense",
            parameters={
                "amount": 120000,
                "currency": "UZS",
                "description": "Kiyim",
                "category": "kiyim",
            },
        ),
        build_capability_registry(),
    )
    assert "120 000" in text and "Kiyim" in text
    assert "Eshitilgan gap: 120 mingga kiyim oldim" in text
    assert "finance.expense" not in text and "To‘g‘ri tushundimmi?" in text
