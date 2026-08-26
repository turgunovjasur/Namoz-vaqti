from datetime import date

import httpx
import pytest

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.namoz_vaqti_api import NamozVaqtiApiClient


def today_payload(*, region_slug: str = "toshkent-shahri") -> dict[str, object]:
    return {
        "meta": {
            "region": {
                "slug": region_slug,
                "name": "Toshkent shahri",
                "parent": "toshkent-shahri",
            },
            "lang": "lotin",
            "period": "today",
            "period_canonical": "today",
            "ym": None,
            "date": "2026-08-26",
            "now": "15:18",
            "offset_min": 0,
            "urls": {},
        },
        "labels": {
            "bomdod": "Bomdod",
            "quyosh": "Quyosh",
            "peshin": "Peshin",
            "asr": "Asr",
            "shom": "Shom",
            "xufton": "Xufton",
        },
        "today": {
            "times": {
                "bomdod": "04:19",
                "quyosh": "05:43",
                "peshin": "12:25",
                "asr": "17:08",
                "shom": "19:10",
                "xufton": "20:30",
            },
            "current": {},
            "next": {},
        },
        "period_table": [],
    }


def month_payload(*, region_slug: str = "toshkent-shahri") -> dict[str, object]:
    payload = today_payload(region_slug=region_slug)
    meta = payload["meta"]
    assert isinstance(meta, dict)
    meta.update({"period": "2026-08", "ym": "2026-08"})
    payload["period_table"] = [
        {
            "date": "26.08.2026",
            "times": {
                "bomdod": "04:19",
                "quyosh": "05:43",
                "peshin": "12:25",
                "asr": "17:08",
                "shom": "19:10",
                "xufton": "20:30",
            },
        },
        {
            "date": "27.08.2026",
            "times": {
                "bomdod": "04:20",
                "quyosh": "05:44",
                "peshin": "12:25",
                "asr": "17:07",
                "shom": "19:08",
                "xufton": "20:28",
            },
        },
    ]
    return payload


async def test_client_requests_today_json_with_verified_provider_slug() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=today_payload())

    async with httpx.AsyncClient(
        base_url="https://namoz-vaqti.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        schedule = await NamozVaqtiApiClient(http_client).get_today("Toshkent")

    assert captured_request is not None
    assert captured_request.url.path == "/"
    assert dict(captured_request.url.params) == {
        "region": "toshkent-shahri",
        "lang": "lotin",
        "period": "today",
        "format": "json",
    }
    assert schedule.date == date(2026, 8, 26)
    assert schedule.region_code == "Toshkent"
    assert schedule.region_name == "Toshkent shahri"
    assert schedule.times.bomdod == "04:19"
    assert schedule.times.xufton == "20:30"


async def test_client_selects_exact_target_date_from_month_table() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=month_payload())

    async with httpx.AsyncClient(
        base_url="https://namoz-vaqti.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        schedule = await NamozVaqtiApiClient(http_client).get_for_date(
            "Toshkent", date(2026, 8, 27)
        )

    assert captured_request is not None
    assert dict(captured_request.url.params) == {
        "region": "toshkent-shahri",
        "lang": "lotin",
        "period": "2026-08",
        "format": "json",
    }
    assert schedule.date == date(2026, 8, 27)
    assert schedule.times.bomdod == "04:20"
    assert schedule.times.xufton == "20:28"


async def test_client_rejects_provider_region_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=today_payload(region_slug="samarqand-shahri"))

    async with httpx.AsyncClient(
        base_url="https://namoz-vaqti.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        with pytest.raises(ExternalServiceError, match="hududi mos emas"):
            await NamozVaqtiApiClient(http_client).get_today("Toshkent")


async def test_client_rejects_month_without_requested_date() -> None:
    payload = month_payload()
    payload["period_table"] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        base_url="https://namoz-vaqti.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        with pytest.raises(ExternalServiceError, match="so‘ralgan sana topilmadi"):
            await NamozVaqtiApiClient(http_client).get_for_date("Toshkent", date(2026, 8, 28))


async def test_client_retries_transient_server_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json=today_payload())

    async with httpx.AsyncClient(
        base_url="https://namoz-vaqti.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        await NamozVaqtiApiClient(http_client, retry_delays=(0.0,)).get_today("Toshkent")

    assert attempts == 2
