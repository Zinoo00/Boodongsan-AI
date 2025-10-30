"""
Seoul Open Data (OA-21285) client used to retrieve live city snapshots.

The official API shape is documented at
https://data.seoul.go.kr/dataList/OA-21285/A/1/datasetView.do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from core.config import settings


@dataclass
class CitySnapshot:
    """Lightweight wrapper around the API response."""

    area: str
    payload: dict[str, Any]
    metadata: dict[str, Any]


class SeoulCityDataService:
    """Async client for the Seoul Open Data OA-21285 endpoint."""

    BASE_URL = "https://openapi.seoul.go.kr:8088"

    def __init__(self) -> None:
        self._api_key = (settings.SEOUL_OPEN_API_KEY or "").strip()
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        if self._client:
            return

        timeout = httpx.Timeout(10.0, connect=5.0)
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=timeout)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_city_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        snapshot = await self._fetch_snapshot(
            location_name=location_name,
            area_code=area_code,
            start_row=start_row,
            end_row=end_row,
        )

        return {
            "area": snapshot.area,
            "data": snapshot.payload,
            "metadata": snapshot.metadata,
        }

    async def get_population_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        snapshot = await self._fetch_snapshot(
            location_name=location_name,
            area_code=area_code,
            start_row=start_row,
            end_row=end_row,
        )

        population_section = snapshot.payload.get("LIVE_PPLTN_STTS", {})
        population = self._unwrap_section(population_section, "LIVE_PPLTN_STTS")
        return {
            "area": snapshot.area,
            "population": population,
            "metadata": snapshot.metadata,
        }

    async def get_commercial_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        snapshot = await self._fetch_snapshot(
            location_name=location_name,
            area_code=area_code,
            start_row=start_row,
            end_row=end_row,
        )

        commercial_section = snapshot.payload.get("LIVE_FCLTY_STTS", {})
        commercial = self._unwrap_section(commercial_section, "LIVE_FCLTY_STTS")
        return {
            "area": snapshot.area,
            "commercial_activity": commercial,
            "metadata": snapshot.metadata,
        }

    async def _fetch_snapshot(
        self,
        *,
        location_name: str | None,
        area_code: str | None,
        start_row: int,
        end_row: int,
    ) -> CitySnapshot:
        if not location_name and not area_code:
            raise ValueError("location_name or area_code must be provided.")

        if location_name and area_code:
            raise ValueError("Only one of location_name or area_code can be specified.")

        if start_row < 1 or end_row < start_row:
            raise ValueError("Invalid row range requested.")

        client = await self._ensure_client()
        api_key = self._api_key or "sample"
        identifier = quote(area_code or location_name or "")
        path = f"/{api_key}/json/citydata/{start_row}/{end_row}/{identifier}"

        response = await client.get(path)
        response.raise_for_status()

        payload = response.json()
        row = self._extract_first_row(payload)

        metadata = {
            "request": {
                "location_name": location_name,
                "area_code": area_code,
                "start_row": start_row,
                "end_row": end_row,
            },
            "using_sample_key": not bool(self._api_key),
        }

        area_name = row.get("AREA_NM") or identifier
        metadata["area_code"] = row.get("AREA_CD")
        return CitySnapshot(area=area_name, payload=row, metadata=metadata)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if not self._client:
            await self.initialize()
        if not self._client:
            raise RuntimeError("SeoulCityDataService is not initialised")
        return self._client

    def _extract_first_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        citydata = payload.get("citydata", {})
        result = citydata.get("RESULT") or {}
        code = result.get("CODE") or result.get("RESULT.CODE")
        if code and code != "INFO-000":
            message = result.get("MESSAGE") or result.get("RESULT.MESSAGE", "Unknown error")
            raise ValueError(f"Seoul Open Data API returned error {code}: {message}")

        rows = citydata.get("row") or citydata.get("CITYDATA") or citydata.get("SeoulRtd.citydata")
        if isinstance(rows, list) and rows:
            return rows[0]

        raise ValueError("Seoul Open Data API returned an empty payload.")

    def _unwrap_section(self, section: Any, key: str) -> list[dict[str, Any]]:
        if isinstance(section, dict):
            value = section.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
        if isinstance(section, list):
            return section
        return []
