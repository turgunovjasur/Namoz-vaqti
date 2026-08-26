"""HTTP adapter for the namoz-vaqti.uz JSON API."""

import asyncio
from collections.abc import Mapping
from datetime import date
from typing import Any

import httpx

from namoz_bot.domain.errors import ExternalServiceError, ScheduleValidationError
from namoz_bot.domain.models import PrayerSchedule, PrayerTimes
from namoz_bot.domain.regions import Region, get_region


class NamozVaqtiApiClient:
    """Fetch validated current-day and dated Uzbekistan prayer schedules."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        retry_delays: tuple[float, ...] = (0.5, 1.5),
    ) -> None:
        self._http_client = http_client
        self._retry_delays = retry_delays

    async def get_today(self, region_code: str) -> PrayerSchedule:
        region = get_region(region_code)
        payload = self._read_payload(
            await self._get_with_retry(
                region,
                period="today",
            )
        )
        self._validate_region(payload, region)
        try:
            meta = payload["meta"]
            today = payload["today"]
            if not isinstance(meta, Mapping) or not isinstance(today, Mapping):
                raise TypeError("meta/today")
            raw_date = meta["date"]
            raw_times = today["times"]
            if not isinstance(raw_date, str):
                raise TypeError("date")
            schedule_date = date.fromisoformat(raw_date)
            times = self._to_times(raw_times)
        except (KeyError, TypeError, ValueError, ScheduleValidationError) as exc:
            raise ExternalServiceError("namoz-vaqti.uz javobi noto‘g‘ri yoki to‘liq emas") from exc
        return self._schedule(region, schedule_date, times)

    async def get_for_date(self, region_code: str, target_date: date) -> PrayerSchedule:
        region = get_region(region_code)
        requested_month = target_date.strftime("%Y-%m")
        payload = self._read_payload(
            await self._get_with_retry(
                region,
                period=requested_month,
            )
        )
        self._validate_region(payload, region)
        try:
            meta = payload["meta"]
            rows = payload["period_table"]
            if not isinstance(meta, Mapping) or not isinstance(rows, list):
                raise TypeError("meta/period_table")
            if meta.get("ym") != requested_month:
                raise ExternalServiceError("namoz-vaqti.uz oy javobi so‘rovga mos emas")
            expected_label = target_date.strftime("%d.%m.%Y")
            row = next(
                item
                for item in rows
                if isinstance(item, Mapping) and item.get("date") == expected_label
            )
            times = self._to_times(row["times"])
        except StopIteration as exc:
            raise ExternalServiceError("namoz-vaqti.uz javobida so‘ralgan sana topilmadi") from exc
        except ExternalServiceError:
            raise
        except (KeyError, TypeError, ValueError, ScheduleValidationError) as exc:
            raise ExternalServiceError("namoz-vaqti.uz javobi noto‘g‘ri yoki to‘liq emas") from exc
        return self._schedule(region, target_date, times)

    async def _get_with_retry(self, region: Region, *, period: str) -> httpx.Response:
        params = {
            "region": region.provider_key,
            "lang": "lotin",
            "period": period,
            "format": "json",
        }
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                response = await self._http_client.get("/", params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == attempts - 1:
                    raise ExternalServiceError("namoz-vaqti.uz bilan aloqa qilib bo‘lmadi") from exc
                await asyncio.sleep(self._retry_delays[attempt])
                continue

            is_transient = response.status_code == 429 or response.status_code >= 500
            if is_transient and attempt < attempts - 1:
                await asyncio.sleep(self._retry_delays[attempt])
                continue
            if response.is_error:
                raise ExternalServiceError(f"namoz-vaqti.uz HTTP xatosi: {response.status_code}")
            return response
        raise ExternalServiceError("namoz-vaqti.uz so‘rovi yakunlanmadi")

    @staticmethod
    def _read_payload(response: httpx.Response) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("namoz-vaqti.uz javobi noto‘g‘ri JSON") from exc
        if not isinstance(payload, Mapping):
            raise ExternalServiceError("namoz-vaqti.uz javobi noto‘g‘ri obyekt")
        return payload

    @staticmethod
    def _validate_region(payload: Mapping[str, Any], region: Region) -> None:
        try:
            meta = payload["meta"]
            if not isinstance(meta, Mapping):
                raise TypeError("meta")
            raw_region = meta["region"]
            if not isinstance(raw_region, Mapping):
                raise TypeError("region")
            provider_slug = raw_region["slug"]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError("namoz-vaqti.uz hudud javobi noto‘g‘ri") from exc
        if provider_slug != region.provider_key:
            raise ExternalServiceError("namoz-vaqti.uz hududi mos emas")

    @staticmethod
    def _to_times(raw_times: object) -> PrayerTimes:
        if not isinstance(raw_times, Mapping):
            raise TypeError("times")
        return PrayerTimes(
            bomdod=str(raw_times["bomdod"]),
            quyosh=str(raw_times["quyosh"]),
            peshin=str(raw_times["peshin"]),
            asr=str(raw_times["asr"]),
            shom=str(raw_times["shom"]),
            xufton=str(raw_times["xufton"]),
        )

    @staticmethod
    def _schedule(region: Region, schedule_date: date, times: PrayerTimes) -> PrayerSchedule:
        return PrayerSchedule(
            date=schedule_date,
            region_code=region.code,
            region_name=region.display_name,
            times=times,
        )
