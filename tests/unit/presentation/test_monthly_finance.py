from datetime import date

from namoz_bot.domain.accounting import LedgerSummary
from namoz_bot.presentation.accounting import _summary_text


def test_monthly_summary_does_not_present_carryover_as_monthly_money():
    text = _summary_text(LedgerSummary(date(2026, 11, 1), 5_000_000, 1_000_000, 0, 2_000_000))
    assert "4 000 000 so‘m" in text
    assert "6 000 000" not in text
    assert "2 000 000" not in text
