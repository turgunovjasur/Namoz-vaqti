from datetime import date

import httpx
import pytest

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.islom_api import IslomApiClient


def valid_payload(*, schedule_date: str = "2026-08-27") -> dict[str, object]:
    return {
        "region": "Toshkent",
        "date": schedule_date,
        "weekday": "Payshanba",
        "hijri_date": {"month": "rabiul avval", "day": 14},
        "times": {
            "tong_saharlik": "04:17",
            "quyosh": "05:42",
            "peshin": "12:25",
            "asr": "17:10",
            "shom_iftor": "19:12",
            "hufton": "20:32",
        },
    }


@pytest.mark.asyncio
async def test_client_requests_daily_endpoint_and_maps_complete_payload() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=valid_payload())

    async with httpx.AsyncClient(
        base_url="https://islomapi.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        schedule = await IslomApiClient(http_client).get_for_date("Toshkent", date(2026, 8, 27))

    assert captured_request is not None
    assert captured_request.url.path == "/api/daily"
    assert dict(captured_request.url.params) == {
        "region": "Toshkent",
        "month": "8",
        "day": "27",
    }
    assert schedule.date == date(2026, 8, 27)
    assert schedule.region_name == "Toshkent"
    assert schedule.times.bomdod == "04:17"
    assert schedule.times.xufton == "20:32"


@pytest.mark.asyncio
async def test_client_retries_transient_server_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json=valid_payload())

    async with httpx.AsyncClient(
        base_url="https://islomapi.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        await IslomApiClient(http_client, retry_delays=(0.0,)).get_for_date(
            "Toshkent", date(2026, 8, 27)
        )

    assert attempts == 2


@pytest.mark.asyncio
async def test_client_does_not_retry_unknown_region() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"error": "not found"})

    async with httpx.AsyncClient(
        base_url="https://islomapi.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        with pytest.raises(ExternalServiceError, match="404"):
            await IslomApiClient(http_client, retry_delays=(0.0, 0.0)).get_for_date(
                "Unknown", date(2026, 8, 27)
            )

    assert attempts == 1


@pytest.mark.asyncio
async def test_client_rejects_incomplete_payload() -> None:
    payload = valid_payload()
    del payload["times"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        base_url="https://islomapi.uz",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        with pytest.raises(ExternalServiceError, match="javobi noto‘g‘ri"):
            await IslomApiClient(http_client).get_for_date("Toshkent", date(2026, 8, 27))
