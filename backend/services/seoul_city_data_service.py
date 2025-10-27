"""
서울 열린데이터 광장의 실시간 도시 데이터 API(OA-21285) 래퍼.

서울 주요 120개 권역에 대한 실시간 인구, 교통, 날씨, 상권 등의 정보를
수집하고 정규화한다. 자세한 문서:
https://data.seoul.go.kr/dataList/OA-21285/A/1/datasetView.do
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from core.config import settings
from core.exceptions import ErrorCode, ExternalServiceError, ValidationError

logger = logging.getLogger(__name__)


class SeoulCityDataService:
    """서울 실시간 도시 데이터 조회용 비동기 클라이언트."""

    BASE_URL = "https://openapi.seoul.go.kr:8088"
    DATASET_NAME = "Seoul Open Data OA-21285"

    def __init__(self) -> None:
        self._api_key = (settings.SEOUL_OPEN_API_KEY or "").strip()
        self._client: httpx.AsyncClient | None = None
        self._using_sample_key = not self._api_key or self._api_key.lower() == "sample"

        if self._using_sample_key:
            logger.warning(
                "SEOUL_OPEN_API_KEY is not configured. Falling back to Seoul Open Data "
                "sample key, which only exposes the '광화문·덕수궁' snapshot."
            )

    async def initialize(self) -> None:
        """내부 HTTP 클라이언트 초기화."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(10.0, connect=5.0, read=10.0),
            )

    async def close(self) -> None:
        """내부 HTTP 클라이언트 종료."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def using_sample_key(self) -> bool:
        return self._using_sample_key

    async def get_city_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        """
        특정 권역의 실시간 도시 데이터를 조회하고 정규화한다.

        Args:
            location_name: 장소명(예: "광화문·덕수궁").
            area_code: 장소 코드(예: "POI009").
            start_row: 조회 시작 행(1부터 시작).
            end_row: 조회 종료 행(포함).
        """

        if (not location_name and not area_code) or (location_name and area_code):
            raise ValidationError(
                message="Provide exactly one of location_name or area_code",
                field_name="identifier",
            )

        if start_row < 1 or end_row < start_row:
            raise ValidationError(
                message="Invalid start/end rows for Seoul city data request",
                details={"start_row": start_row, "end_row": end_row},
            )

        identifier = area_code or location_name or ""
        payload = await self._fetch(identifier=identifier, start_row=start_row, end_row=end_row)
        normalized = self._normalise_payload(payload)
        normalized["metadata"]["using_sample_key"] = self.using_sample_key
        return normalized

    async def get_population_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        """OA-21778(실시간 인구 데이터)에 맞춘 요약 결과 반환."""

        snapshot = await self.get_city_snapshot(
            location_name=location_name,
            area_code=area_code,
            start_row=start_row,
            end_row=end_row,
        )
        population = snapshot.get("population")
        if not population:
            raise ExternalServiceError(
                message="Seoul Open Data population payload is empty",
                service_name=f"{self.DATASET_NAME} (population subset)",
                error_code=ErrorCode.EXTERNAL_API_ERROR,
            )

        return {
            "area": snapshot.get("area"),
            "population": population,
            "metadata": snapshot.get("metadata", {}),
        }

    async def get_commercial_snapshot(
        self,
        *,
        location_name: str | None = None,
        area_code: str | None = None,
        start_row: int = 1,
        end_row: int = 5,
    ) -> dict[str, Any]:
        """OA-22385(실시간 상권 데이터)에 맞춘 요약 결과 반환."""

        snapshot = await self.get_city_snapshot(
            location_name=location_name,
            area_code=area_code,
            start_row=start_row,
            end_row=end_row,
        )
        commercial = snapshot.get("commercial_activity")
        if not commercial:
            raise ExternalServiceError(
                message="Seoul Open Data commercial payload is empty",
                service_name=f"{self.DATASET_NAME} (commercial subset)",
                error_code=ErrorCode.EXTERNAL_API_ERROR,
            )

        return {
            "area": snapshot.get("area"),
            "commercial_activity": commercial,
            "metadata": snapshot.get("metadata", {}),
        }

    async def _fetch(self, identifier: str, start_row: int, end_row: int) -> dict[str, Any]:
        client = await self._ensure_client()
        api_key = self._api_key or "sample"
        path = f"/{api_key}/json/citydata/{start_row}/{end_row}/{quote(identifier)}"

        try:
            response = await client.get(path)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_code = ErrorCode.EXTERNAL_API_ERROR
            if status_code == 429:
                error_code = ErrorCode.EXTERNAL_API_RATE_LIMIT
            elif status_code in (500, 503, 504):
                error_code = ErrorCode.EXTERNAL_API_TIMEOUT

            raise ExternalServiceError(
                message="Seoul Open Data request failed",
                service_name=self.DATASET_NAME,
                status_code=status_code,
                error_code=error_code,
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                message="Seoul Open Data request error",
                service_name=self.DATASET_NAME,
                error_code=ErrorCode.EXTERNAL_API_TIMEOUT,
                cause=exc,
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                message="Failed to decode Seoul city data response",
                service_name=self.DATASET_NAME,
                cause=exc,
            ) from exc

        result = data.get("RESULT", {})
        result_code = result.get("RESULT.CODE")
        if result_code != "INFO-000":
            message = result.get("RESULT.MESSAGE", "Unknown error")
            raise ExternalServiceError(
                message=f"Seoul Open Data API error: {message}",
                service_name=self.DATASET_NAME,
                error_code=ErrorCode.EXTERNAL_API_ERROR,
                details={"result_code": result_code},
            )

        citydata = data.get("CITYDATA")
        if not citydata:
            raise ExternalServiceError(
                message="Seoul Open Data response did not include CITYDATA payload",
                service_name=self.DATASET_NAME,
                error_code=ErrorCode.EXTERNAL_API_ERROR,
            )

        return citydata

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.initialize()
        assert self._client is not None
        return self._client

    # ------------------------------------------------------------------
    # 정규화 함수
    # ------------------------------------------------------------------

    def _normalise_payload(self, citydata: dict[str, Any]) -> dict[str, Any]:
        area_name = citydata.get("AREA_NM")
        area_code = citydata.get("AREA_CD")
        retrieved_at = datetime.utcnow().isoformat()

        payload: dict[str, Any] = {
            "area": {
                "name": area_name,
                "code": area_code,
            },
            "population": self._normalise_population(citydata.get("LIVE_PPLTN_STTS")),
            "traffic": self._normalise_traffic(citydata.get("ROAD_TRAFFIC_STTS")),
            "public_transport": {
                "subway": self._normalise_subway(citydata.get("SUB_STTS"), citydata.get("LIVE_SUB_PPLTN")),
                "bus": self._normalise_bus(citydata.get("BUS_STN_STTS"), citydata.get("LIVE_BUS_PPLTN")),
            },
            "parking": self._normalise_parking(citydata.get("PRK_STTS")),
            "bike_sharing": self._normalise_bike(citydata.get("SBIKE_STTS")),
            "weather": self._normalise_weather(citydata.get("WEATHER_STTS")),
            "charging_stations": self._normalise_chargers(citydata.get("CHARGER_STTS")),
            "events": self._normalise_events(citydata.get("EVENT_STTS")),
            "commercial_activity": self._normalise_commercial(citydata.get("LIVE_CMRCL_STTS")),
            "metadata": {
                "retrieved_at": retrieved_at,
                "source": self.DATASET_NAME,
            },
        }

        additional_sections = {}
        for key in [
            "ACDNT_CNTRL_STTS",
            "LIVE_DST_MESSAGE",
            "LIVE_YNA_NEWS",
        ]:
            value = citydata.get(key)
            if value:
                additional_sections[key.lower()] = value

        if additional_sections:
            payload["additional_sections"] = additional_sections

        return payload

    def _normalise_population(self, data: list[dict[str, Any]] | None) -> dict[str, Any] | None:
        if not data:
            return None

        entry = data[0]
        forecast = []
        for item in entry.get("FCST_PPLTN", [])[:8]:
            forecast.append(
                {
                    "time": self._parse_time(item.get("FCST_TIME")),
                    "congestion_level": item.get("FCST_CONGEST_LVL"),
                    "population_min": self._to_int(item.get("FCST_PPLTN_MIN")),
                    "population_max": self._to_int(item.get("FCST_PPLTN_MAX")),
                }
            )

        age_distribution = {
            "0s": self._to_float(entry.get("PPLTN_RATE_0")),
            "10s": self._to_float(entry.get("PPLTN_RATE_10")),
            "20s": self._to_float(entry.get("PPLTN_RATE_20")),
            "30s": self._to_float(entry.get("PPLTN_RATE_30")),
            "40s": self._to_float(entry.get("PPLTN_RATE_40")),
            "50s": self._to_float(entry.get("PPLTN_RATE_50")),
            "60s": self._to_float(entry.get("PPLTN_RATE_60")),
            "70s": self._to_float(entry.get("PPLTN_RATE_70")),
        }

        return {
            "congestion_level": entry.get("AREA_CONGEST_LVL"),
            "message": entry.get("AREA_CONGEST_MSG"),
            "population_min": self._to_int(entry.get("AREA_PPLTN_MIN")),
            "population_max": self._to_int(entry.get("AREA_PPLTN_MAX")),
            "gender_ratio": {
                "male_rate": self._to_float(entry.get("MALE_PPLTN_RATE")),
                "female_rate": self._to_float(entry.get("FEMALE_PPLTN_RATE")),
            },
            "resident_rate": self._to_float(entry.get("RESNT_PPLTN_RATE")),
            "non_resident_rate": self._to_float(entry.get("NON_RESNT_PPLTN_RATE")),
            "reported_at": self._parse_time(entry.get("PPLTN_TIME")),
            "forecast_available": entry.get("FCST_YN") == "Y",
            "forecast": forecast,
            "age_distribution": age_distribution,
        }

    def _normalise_traffic(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not data:
            return None

        avg = data.get("AVG_ROAD_DATA") or {}
        segments = []
        for item in data.get("ROAD_TRAFFIC_STTS", [])[:8]:
            segments.append(
                {
                    "road_name": item.get("ROAD_NM"),
                    "speed_kmh": self._to_float(item.get("SPD")),
                    "traffic_index": item.get("IDX"),
                    "distance_m": self._to_float(item.get("DIST")),
                }
            )

        return {
            "message": avg.get("ROAD_MSG"),
            "traffic_index": avg.get("ROAD_TRAFFIC_IDX"),
            "average_speed_kmh": self._to_float(avg.get("ROAD_TRAFFIC_SPD")),
            "reported_at": self._parse_time(avg.get("ROAD_TRAFFIC_TIME")),
            "segments": segments,
        }

    def _normalise_parking(self, data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not data:
            return []

        entries = []
        for item in data[:8]:
            entries.append(
                {
                    "name": item.get("PRK_NM"),
                    "code": item.get("PRK_CD"),
                    "type": item.get("PRK_TYPE"),
                    "capacity": self._to_int(item.get("CPCTY")),
                    "current_count": self._to_int(item.get("CUR_PRK_CNT")),
                    "is_open": item.get("CUR_PRK_YN") == "Y",
                    "updated_at": self._parse_time(item.get("CUR_PRK_TIME")),
                    "paid": item.get("PAY_YN") == "Y",
                    "base_rate": item.get("RATES"),
                    "base_time": item.get("TIME_RATES"),
                    "extra_rate": item.get("ADD_RATES"),
                    "extra_time": item.get("ADD_TIME_RATES"),
                    "address": item.get("ADDRESS") or item.get("ROAD_ADDR"),
                    "coordinates": {
                        "latitude": self._to_float(item.get("LAT")),
                        "longitude": self._to_float(item.get("LNG")),
                    },
                }
            )
        return entries

    def _normalise_subway(
        self,
        stations: list[dict[str, Any]] | None,
        stats: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not stations and not stats:
            return None

        return {
            "stations": [
                {
                    "name": item.get("SUB_STN_NM"),
                    "line": item.get("SUB_STN_LINE"),
                    "address": item.get("SUB_STN_RADDR") or item.get("SUB_STN_JIBUN"),
                }
                for item in (stations or [])[:5]
            ],
            "ridership_summary": stats or {},
        }

    def _normalise_bus(
        self,
        stations: list[dict[str, Any]] | None,
        stats: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not stations and not stats:
            return None

        return {
            "stations": [
                {
                    "name": item.get("BUS_STN_NM"),
                    "ars_id": item.get("BUS_ARS_ID"),
                    "message": item.get("BUS_RESULT_MSG"),
                }
                for item in (stations or [])[:5]
            ],
            "ridership_summary": stats or {},
        }

    def _normalise_bike(self, data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not data:
            return []

        return [
            {
                "spot_name": item.get("SBIKE_SPOT_NM"),
                "spot_id": item.get("SBIKE_SPOT_ID"),
                "shared": self._to_float(item.get("SBIKE_SHARED")),
                "parking_count": self._to_int(item.get("SBIKE_PARKING_CNT")),
                "rack_count": self._to_int(item.get("SBIKE_RACK_CNT")),
            }
            for item in data[:5]
        ]

    def _normalise_weather(self, data: list[dict[str, Any]] | None) -> dict[str, Any] | None:
        if not data:
            return None

        entry = data[0]
        forecast = []
        for item in entry.get("FCST24HOURS", [])[:12]:
            forecast.append(
                {
                    "forecast_time": self._parse_time(item.get("FCST_DT")),
                    "sky_status": item.get("SKY_STTS"),
                    "temperature_c": self._to_float(item.get("TEMP")),
                    "precipitation": item.get("PRECIPITATION"),
                    "precipitation_type": item.get("PRECPT_TYPE"),
                    "rain_chance_percent": self._to_float(item.get("RAIN_CHANCE")),
                }
            )

        return {
            "reported_at": self._parse_time(entry.get("WEATHER_TIME")),
            "temperature_c": self._to_float(entry.get("TEMP")),
            "sensible_temp_c": self._to_float(entry.get("SENSIBLE_TEMP")),
            "humidity": self._to_float(entry.get("HUMIDITY")),
            "wind_direction": entry.get("WIND_DIRCT"),
            "wind_speed": self._to_float(entry.get("WIND_SPD")),
            "precipitation": entry.get("PRECIPITATION"),
            "precipitation_type": entry.get("PRECPT_TYPE"),
            "precipitation_message": entry.get("PCP_MSG"),
            "sunrise": entry.get("SUNRISE"),
            "sunset": entry.get("SUNSET"),
            "uv_index": entry.get("UV_INDEX"),
            "uv_level": entry.get("UV_INDEX_LVL"),
            "uv_message": entry.get("UV_MSG"),
            "air_quality": {
                "pm25": self._to_float(entry.get("PM25")),
                "pm25_index": entry.get("PM25_INDEX"),
                "pm10": self._to_float(entry.get("PM10")),
                "pm10_index": entry.get("PM10_INDEX"),
                "air_index": entry.get("AIR_IDX"),
                "air_main": entry.get("AIR_IDX_MAIN"),
                "air_value": entry.get("AIR_IDX_MVL"),
                "air_message": entry.get("AIR_MSG"),
            },
            "forecast": forecast,
            "news": entry.get("NEWS_LIST", []),
        }

    def _normalise_chargers(self, data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not data:
            return []

        return [
            {
                "station_name": item.get("STAT_NM"),
                "station_id": item.get("STAT_ID"),
                "address": item.get("STAT_ADDR"),
                "availability": item.get("STAT_LIMITYN"),
                "usage_time": item.get("STAT_USETIME"),
                "is_paid": item.get("STAT_PARKPAY") == "Y",
                "details": item.get("CHARGER_DETAILS"),
            }
            for item in data[:5]
        ]

    def _normalise_events(self, data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not data:
            return []

        return [
            {
                "name": item.get("EVENT_NM"),
                "period": item.get("EVENT_PERIOD"),
                "place": item.get("EVENT_PLACE"),
                "is_paid": item.get("PAY_YN") == "Y",
                "url": item.get("URL"),
                "thumbnail": item.get("THUMBNAIL"),
                "details": item.get("EVENT_ETC_DETAIL"),
            }
            for item in data[:5]
        ]

    def _normalise_commercial(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not data:
            return None

        return {
            "commercial_level": data.get("AREA_CMRCL_LVL"),
            "sales_banding": data.get("CMRCL_RSB"),
            "payment_count": self._to_int(data.get("AREA_SH_PAYMENT_CNT")),
            "payment_amount_range": {
                "min": self._to_int(data.get("AREA_SH_PAYMENT_AMT_MIN")),
                "max": self._to_int(data.get("AREA_SH_PAYMENT_AMT_MAX")),
            },
            "gender_ratio": {
                "male_rate": self._to_float(data.get("CMRCL_MALE_RATE")),
                "female_rate": self._to_float(data.get("CMRCL_FEMALE_RATE")),
            },
            "age_distribution": {
                "10s": self._to_float(data.get("CMRCL_10_RATE")),
                "20s": self._to_float(data.get("CMRCL_20_RATE")),
                "30s": self._to_float(data.get("CMRCL_30_RATE")),
                "40s": self._to_float(data.get("CMRCL_40_RATE")),
                "50s": self._to_float(data.get("CMRCL_50_RATE")),
                "60s": self._to_float(data.get("CMRCL_60_RATE")),
            },
            "customer_type_ratio": {
                "personal": self._to_float(data.get("CMRCL_PERSONAL_RATE")),
                "corporation": self._to_float(data.get("CMRCL_CORPORATION_RATE")),
            },
            "reported_at": self._parse_time(data.get("CMRCL_TIME")),
        }

    # ---------------------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------------------

    def _to_int(self, value: Any) -> int | None:
        if value in (None, "", "-", " "):
            return None
        try:
            return int(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None

    def _to_float(self, value: Any) -> float | None:
        if value in (None, "", "-", " "):
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    def _parse_time(self, value: Any) -> str | None:
        if not value or not isinstance(value, str):
            return None

        value = value.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        return value or None
