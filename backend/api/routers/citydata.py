"""
Simplified Seoul city data endpoints.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_citydata_service
from services.seoul_city_data_service import SeoulCityDataService

router = APIRouter()


def _resolve_service(service: SeoulCityDataService | None) -> SeoulCityDataService:
    if service is None:
        raise HTTPException(status_code=503, detail="City data service is not ready")
    return service


@router.get("")
async def get_city_snapshot(
    service: SeoulCityDataService | None = Depends(get_citydata_service),
    location: str | None = Query(default=None),
    area_code: str | None = Query(default=None),
    start: int = Query(default=1),
    end: int = Query(default=5),
) -> dict:
    svc = _resolve_service(service)
    try:
        return await svc.get_city_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Seoul Open Data request failed") from exc


@router.get("/population")
async def get_population_snapshot(
    service: SeoulCityDataService | None = Depends(get_citydata_service),
    location: str | None = Query(default=None),
    area_code: str | None = Query(default=None),
    start: int = Query(default=1),
    end: int = Query(default=5),
) -> dict:
    svc = _resolve_service(service)
    try:
        return await svc.get_population_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Seoul Open Data request failed") from exc


@router.get("/commercial")
async def get_commercial_snapshot(
    service: SeoulCityDataService | None = Depends(get_citydata_service),
    location: str | None = Query(default=None),
    area_code: str | None = Query(default=None),
    start: int = Query(default=1),
    end: int = Query(default=5),
) -> dict:
    svc = _resolve_service(service)
    try:
        return await svc.get_commercial_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Seoul Open Data request failed") from exc
