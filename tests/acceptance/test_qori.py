from aiogram.methods import EditMessageText, SendDocument, SendMessage, SendPhoto

from namoz_bot.config import Settings
from namoz_bot.infrastructure.orm import Base
from namoz_bot.main import create_application
from namoz_bot.presentation.keyboards import QORI_LABEL
from namoz_bot.qori.corpus import chapters
from tests.acceptance.test_reminder_journey import Journey


class QoriJourney(Journey):
    @property
    def last(self):
        return next(
            c
            for c in reversed(self.session.calls)
            if isinstance(c, (EditMessageText, SendDocument, SendMessage, SendPhoto))
        )


async def test_personal_selection_and_full_reading(tmp_path):
    app = create_application(
        Settings(
            _env_file=None,
            qori_enabled=True,
            telegram_bot_token="123456:TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
            main_agent_enabled=False,
        )
    )
    try:
        async with app.db_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await app.bot.session.close()
        j = QoriJourney(app)
        j.seed_legacy_access = False
        await j.text("/start")
        assert QORI_LABEL in [b.text for row in j.session.reply_keyboards[7].keyboard for b in row]
        await j.text(QORI_LABEL)

        def labels():
            return [b.text for row in j.last.reply_markup.inline_keyboard for b in row]

        assert labels() == ["TANLANGAN SURALAR", "Sura qo‘shish"]
        await j.click("TANLANGAN SURALAR")
        assert "Hali sura tanlamagansiz" in j.last.text
        await j.click("Sura qo‘shish")
        await j.click("Baqara")
        await j.click("Fotiha")
        assert "✅ Baqara" in labels()
        assert "Baqara" not in j.last.text
        seen = []
        while True:
            seen.extend(
                b.text.removeprefix("✅ ")
                for row in j.last.reply_markup.inline_keyboard
                for b in row
                if b.callback_data.startswith(("qori:add:", "qori:remove:"))
            )
            if "Keyingi ➡️" not in labels():
                break
            await j.click("Keyingi ➡️")
        assert seen == [surah.name for surah in chapters()]
        await j.click("Nos")
        await j.text("/start", user=9)
        await j.text(QORI_LABEL, user=9)
        await j.click("TANLANGAN SURALAR", user=9)
        assert "Hali sura tanlamagansiz" in j.last.text
        # A fresh menu clears the previous FSM draft; selections must survive it.
        await j.text("/qori")
        await j.click("TANLANGAN SURALAR")
        assert labels()[:3] == ["Fotiha", "Baqara", "Nos"]
        await j.click("Nos")
        assert isinstance(j.last, SendDocument)
        assert j.last.document.filename == "Nos.html"
        assert all(v in j.last.document.data.decode() for v in chapters()[113].verses)
        assert not any(isinstance(c, SendPhoto) for c in j.session.calls)
        await j.click("⬅️ TANLANGAN SURALAR")
        await j.click("Sura qo‘shish")
        await j.click("✅ Baqara")
        await j.click("TANLANGAN SURALAR")
        assert "Baqara" not in labels()
        assert labels()[:2] == ["Fotiha", "Nos"]
    finally:
        await app.close()


def test_complete_corpus_and_long_reading_preserves_each_verse():
    all_surahs = chapters()
    assert len(all_surahs) == 114 and all_surahs[-1].name == "Nos"
    assert sum(len(s.verses) for s in all_surahs) == 6236
    from namoz_bot.qori.reading import reading_html

    for surah in all_surahs:
        html = reading_html(surah).decode()
        assert html.count('class="verse"') == len(surah.verses)
        assert all(f'lang="ar">{verse}</p>' in html for verse in surah.verses)
