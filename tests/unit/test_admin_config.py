import pytest
from pydantic import ValidationError

from namoz_bot.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example",
        "https://u:p@admin.example",
        "https://admin.example/path",
        "https://admin.example/#secret",
        "https://admin.example/?key=x",
    ],
)
def test_admin_url_rejects_public_plaintext_or_url_credentials(url):
    with pytest.raises(ValidationError):
        Settings(
            telegram_bot_token="123:test", database_url="unused", admin_web_url=url, _env_file=None
        )


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8088", "http://localhost:8088", "https://admin.example"]
)
def test_admin_url_allows_loopback_or_public_https(url):
    assert (
        Settings(
            telegram_bot_token="123:test", database_url="unused", admin_web_url=url, _env_file=None
        ).admin_web_url
        == url
    )


def test_admin_url_normalizes_browser_origin():
    settings = Settings(
        telegram_bot_token="123:test",
        database_url="unused",
        admin_web_url="HTTPS://ADMIN.EXAMPLE:443/",
        _env_file=None,
    )
    assert settings.admin_web_url == "https://admin.example"
