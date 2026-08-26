"""HTTP adapter for islomapi.uz prayer schedules."""

import asyncio
from collections.abc import Mapping
from datetime import date
from typing import Any

import httpx

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.models import PrayerSchedule, PrayerTimes
from namoz_bot.domain.regions import get_region


class IslomApiClient:
    """Fetch and translate IslomAPI responses into domain schedules."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        retry_delays: tuple[float, ...] = (0.5, 1.5),
    ) -> None:
        self._http_client = http_client
        self._retry_delays = retry_delays

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        response = await self._get_with_retry(
            "/api/daily",
            params={
                "region": region_code,
                "month": target_date.month,
                "day": target_date.day,
            },
        )
        payload = self._read_payload(response)
        return self._to_schedule(payload, requested_region_code=region_code)

    async def _get_with_retry(
        self,
        path: str,
        *,
        params: Mapping[str, str | int],
    ) -> httpx.Response:
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                response = await self._http_client.get(path, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == attempts - 1:
                    raise ExternalServiceError("IslomAPI bilan aloqa qilib bo‘lmadi") from exc
                await asyncio.sleep(self._retry_delays[attempt])
                continue

            is_transient = response.status_code == 429 or response.status_code >= 500
            if is_transient and attempt < attempts - 1:
                await asyncio.sleep(self._retry_delays[attempt])
                continue
            if response.is_error:
                raise ExternalServiceError(f"IslomAPI HTTP xatosi: {response.status_code}")
            return response

        raise ExternalServiceError("IslomAPI so‘rovi yakunlanmadi")

    @staticmethod
    def _read_payload(response: httpx.Response) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("IslomAPI javobi noto‘g‘ri JSON") from exc
        if not isinstance(payload, Mapping):
            raise ExternalServiceError("IslomAPI javobi noto‘g‘ri obyekt")
        return payload

    @staticmethod
    def _to_schedule(
        payload: Mapping[str, Any],
        *,
        requested_region_code: str,
    ) -> PrayerSchedule:
        try:
            payload_region = payload["region"]
            payload_date = payload["date"]
            raw_times = payload["times"]
            if not isinstance(payload_region, str):
                raise TypeError("region")
            if not isinstance(payload_date, str):
                raise TypeError("date")
            if not isinstance(raw_times, Mapping):
                raise TypeError("times")
            times = PrayerTimes(
                bomdod=str(raw_times["tong_saharlik"]),
                quyosh=str(raw_times["quyosh"]),
                peshin=str(raw_times["peshin"]),
                asr=str(raw_times["asr"]),
                shom=str(raw_times["shom_iftor"]),
                xufton=str(raw_times["hufton"]),
            )
            schedule_date = date.fromisoformat(payload_date)
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError("IslomAPI javobi noto‘g‘ri yoki to‘liq emas") from exc

        try:
            region_name = get_region(requested_region_code).display_name
        except LookupError:
            region_name = requested_region_code

        return PrayerSchedule(
            date=schedule_date,
            region_code=payload_region,
            region_name=region_name,
            times=times,
        )
