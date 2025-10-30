"""
Property router backed by DataService (OpenSearch).
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_data_service

if TYPE_CHECKING:
    from services.data_service import DataService

router = APIRouter()


class PropertySearchRequest(BaseModel):
    """Property search filters."""

    district: str | None = Field(None, description="자치구 (예: 강남구)")
    dong: str | None = Field(None, description="동 (예: 역삼동)")
    property_type: str | None = Field(None, description="부동산 유형 (아파트, 오피스텔 등)")
    transaction_type: str | None = Field(None, description="거래 유형 (매매/전세/월세)")
    price_min: int | None = Field(None, description="최소 가격")
    price_max: int | None = Field(None, description="최대 가격")
    area_min: float | None = Field(None, description="최소 전용면적(㎡)")
    area_max: float | None = Field(None, description="최대 전용면적(㎡)")
    room_count: int | None = Field(None, description="방 개수")
    listing_status: str | None = Field("active", description="매물 상태 (active, hidden 등)")


class PropertyListResponse(BaseModel):
    """Paginated property list."""

    properties: list[dict[str, Any]]
    total_count: int
    filters: dict[str, Any]


@router.post("/search", response_model=PropertyListResponse)
async def search_properties(
    request: PropertySearchRequest,
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> PropertyListResponse:
    """Search properties with flexible filters."""
    filters = {k: v for k, v in request.model_dump().items() if v not in (None, "")}
    results = await data_service.search_properties(filters=filters)

    return PropertyListResponse(
        properties=results,
        total_count=len(results),
        filters=filters,
    )


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    data_service: Annotated["DataService", Depends(get_data_service)],
    district: str | None = Query(None, description="자치구 필터"),
    property_type: str | None = Query(None, description="부동산 유형"),
    transaction_type: str | None = Query(None, description="거래 유형"),
    limit: int = Query(20, ge=1, le=100, description="최대 조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
) -> PropertyListResponse:
    """Return a window of properties."""
    filters = {
        "district": district,
        "property_type": property_type,
        "transaction_type": transaction_type,
    }
    filters = {k: v for k, v in filters.items() if v}

    results = await data_service.search_properties(filters=filters, limit=limit, offset=offset)

    return PropertyListResponse(
        properties=results,
        total_count=len(results),
        filters={"limit": limit, "offset": offset, **filters},
    )


@router.get("/{property_id}")
async def get_property_detail(
    property_id: str,
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> dict[str, Any]:
    """Return a single property."""
    property_record = await data_service.get_property(property_id)
    if not property_record:
        raise HTTPException(status_code=404, detail="해당 매물을 찾을 수 없습니다.")
    return {"property": property_record}


@router.get("/regions/list")
async def get_regions(
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> dict[str, Any]:
    """Return region summary derived from current properties."""
    properties = await data_service.search_properties(limit=200)
    counter = Counter()
    for item in properties:
        district = item.get("district") or item.get("sigungu")
        if district:
            counter[district] += 1

    regions = [{"name": name, "count": count} for name, count in counter.most_common()]
    return {"regions": regions, "total_regions": len(regions)}


@router.get("/types/list")
async def get_property_types(
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> dict[str, Any]:
    """Return property type distribution."""
    properties = await data_service.search_properties(limit=200)
    counter = Counter(prop.get("property_type", "기타") for prop in properties)
    types = [
        {"type": prop_type, "count": count}
        for prop_type, count in counter.most_common()
    ]
    return {"property_types": types, "total_types": len(types)}
