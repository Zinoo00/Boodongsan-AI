"""
Property Service for Korean Real Estate RAG AI Chatbot
Handles property-related business logic
"""

import logging
from typing import Any

from ..models.property import (
    PropertyFilter,
    PropertyResponse,
)

logger = logging.getLogger(__name__)

class PropertyService:
    """Service for property-related operations"""
    
    def __init__(self):
        pass
    
    async def search_properties(
        self,
        filter: PropertyFilter,
        limit: int = 10,
        offset: int = 0
    ) -> list[PropertyResponse]:
        """부동산 검색 (간단한 텍스트 쿼리)"""
        try:
            # 임시 더미 데이터 반환
            dummy_properties = [
                {
                    "id": "prop_001",
                    "title": "강남구 역삼동 아파트",
                    "district": "강남구",
                    "dong": "역삼동",
                    "price": 500000000,
                    "area_exclusive": 84.32
                },
                {
                    "id": "prop_002",
                    "title": "서초구 서초동 오피스텔", 
                    "district": "서초구",
                    "dong": "서초동",
                    "price": 50000000,
                    "area_exclusive": 33.12
                }
            ]
            
            return dummy_properties
            
        except Exception as e:
            logger.error(f"부동산 검색 실패: {str(e)}")
            return []
    
    async def search_properties_by_criteria(
        self, 
        criteria: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """조건 기반 부동산 검색"""
        try:
            # 실제로는 데이터베이스 쿼리 실행
            # 여기서는 임시 더미 데이터 반환
            
            dummy_properties = [
                {
                    "id": "prop_001",
                    "title": "강남구 역삼동 아파트",
                    "property_type": "아파트",
                    "district": "강남구",
                    "dong": "역삼동",
                    "price": 500000000,
                    "area_exclusive": 84.32,
                    "room_count": 3,
                    "year_built": 2018
                },
                {
                    "id": "prop_002",
                    "title": "서초구 서초동 오피스텔",
                    "property_type": "오피스텔",
                    "district": "서초구", 
                    "dong": "서초동",
                    "price": 50000000,
                    "area_exclusive": 33.12,
                    "room_count": 1,
                    "year_built": 2020
                },
                {
                    "id": "prop_003",
                    "title": "송파구 잠실동 아파트",
                    "property_type": "아파트",
                    "district": "송파구",
                    "dong": "잠실동", 
                    "price": 1200000000,
                    "area_exclusive": 114.32,
                    "room_count": 4,
                    "year_built": 2015
                }
            ]
            
            # 간단한 필터링
            filtered_properties = []
            for prop in dummy_properties:
                match = True
                
                if criteria.get("region") and criteria["region"] not in prop["district"]:
                    match = False
                if criteria.get("property_type") and criteria["property_type"] != prop["property_type"]:
                    match = False
                if criteria.get("budget_max") and prop["price"] > criteria["budget_max"]:
                    match = False
                if criteria.get("room_count") and prop["room_count"] != criteria["room_count"]:
                    match = False
                    
                if match:
                    filtered_properties.append(prop)
            
            return filtered_properties
            
        except Exception as e:
            logger.error(f"조건 기반 부동산 검색 실패: {str(e)}")
            return []