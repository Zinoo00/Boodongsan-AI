"""
Property models for Korean Real Estate data
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY

from models.base import Base, BaseSchema, TimestampMixin


class PropertyType(str, Enum):
    """Property types"""

    APARTMENT = "아파트"
    VILLA = "빌라"
    OFFICETEL = "오피스텔"
    SINGLE_HOUSE = "단독주택"
    TOWNHOUSE = "연립주택"
    STUDIO = "원룸"


class TransactionType(str, Enum):
    """Transaction types"""

    SALE = "매매"
    JEONSE = "전세"
    MONTHLY_RENT = "월세"


class Property(Base):
    """Property database model"""

    __tablename__ = "properties"

    # Basic property information
    address = Column(String(500), nullable=False, index=True)
    detailed_address = Column(String(500))
    postal_code = Column(String(10))

    # Location information
    sido = Column(String(50), nullable=False, index=True)  # 시도
    sigungu = Column(String(50), nullable=False, index=True)  # 시군구
    dong = Column(String(50), nullable=False, index=True)  # 동
    jibun = Column(String(100))  # 지번

    # Property details
    property_type = Column(String(20), nullable=False, index=True)
    building_name = Column(String(200))
    room_count = Column(Integer)  # 방 개수
    bathroom_count = Column(Integer)  # 화장실 개수
    area_m2 = Column(Float, nullable=False)  # 면적 (제곱미터)
    area_pyeong = Column(Float)  # 면적 (평)

    # Building information
    building_year = Column(Integer)  # 건축년도
    floor = Column(Integer)  # 층수
    total_floors = Column(Integer)  # 총 층수

    # Transaction information
    transaction_type = Column(String(10), nullable=False, index=True)
    price = Column(Integer, nullable=False, index=True)  # 가격 (원)
    deposit = Column(Integer)  # 보증금 (전세/월세)
    monthly_rent = Column(Integer)  # 월세
    maintenance_fee = Column(Integer)  # 관리비

    # Transaction date
    transaction_date = Column(DateTime, index=True)
    registration_date = Column(DateTime, default=datetime.utcnow)

    # Additional information
    parking_available = Column(Boolean, default=False)
    elevator_available = Column(Boolean, default=False)

    # Coordinate information
    latitude = Column(Float)
    longitude = Column(Float)

    # Infrastructure data (JSON)
    transportation = Column(JSON)  # 교통 정보
    education = Column(JSON)  # 교육 시설
    convenience = Column(JSON)  # 편의 시설

    # Data source
    data_source = Column(String(100))  # 데이터 출처
    source_id = Column(String(100))  # 원본 ID

    # Additional metadata
    description = Column(Text)
    features = Column(ARRAY(String))  # 특징 리스트
    images = Column(ARRAY(String))  # 이미지 URL 리스트

    # Search optimization
    search_vector = Column(Text)  # 검색용 벡터 임베딩 ID

    # Indexes
    __table_args__ = (
        Index("idx_location", "sido", "sigungu", "dong"),
        Index("idx_property_type_transaction", "property_type", "transaction_type"),
        Index("idx_price_range", "transaction_type", "price"),
        Index("idx_area_range", "area_m2"),
        Index("idx_building_year", "building_year"),
        Index("idx_coordinates", "latitude", "longitude"),
    )


class PropertyFilter(BaseModel):
    """Property search filter"""

    # Location filters
    sido: str | None = None
    sigungu: str | None = None
    dong: str | None = None

    # Property type filter
    property_types: list[PropertyType] | None = None
    transaction_types: list[TransactionType] | None = None

    # Price filters
    min_price: int | None = None
    max_price: int | None = None
    min_deposit: int | None = None
    max_deposit: int | None = None
    max_monthly_rent: int | None = None

    # Area filters
    min_area_m2: float | None = None
    max_area_m2: float | None = None
    min_area_pyeong: float | None = None
    max_area_pyeong: float | None = None

    # Room filters
    min_room_count: int | None = None
    max_room_count: int | None = None

    # Building filters
    min_building_year: int | None = None
    max_building_year: int | None = None
    min_floor: int | None = None
    max_floor: int | None = None

    # Feature filters
    parking_required: bool | None = None
    elevator_required: bool | None = None

    # Location filters (coordinates)
    center_lat: float | None = None
    center_lng: float | None = None
    radius_km: float | None = None

    # Date filters
    transaction_date_from: datetime | None = None
    transaction_date_to: datetime | None = None


class PropertyBase(BaseSchema):
    """Base property schema"""

    address: str = Field(..., description="Property address")
    detailed_address: str | None = None
    sido: str = Field(..., description="시도")
    sigungu: str = Field(..., description="시군구")
    dong: str = Field(..., description="동")
    property_type: PropertyType = Field(..., description="Property type")
    transaction_type: TransactionType = Field(..., description="Transaction type")
    area_m2: float = Field(..., gt=0, description="Area in square meters")
    price: int = Field(..., ge=0, description="Price in KRW")


class PropertyCreate(PropertyBase):
    """Property creation schema"""

    building_name: str | None = None
    room_count: int | None = Field(None, ge=0)
    bathroom_count: int | None = Field(None, ge=0)
    area_pyeong: float | None = Field(None, gt=0)
    building_year: int | None = Field(None, ge=1900, le=2030)
    floor: int | None = Field(None, ge=-10, le=200)
    total_floors: int | None = Field(None, ge=1, le=200)
    deposit: int | None = Field(None, ge=0)
    monthly_rent: int | None = Field(None, ge=0)
    maintenance_fee: int | None = Field(None, ge=0)
    transaction_date: datetime | None = None
    parking_available: bool | None = False
    elevator_available: bool | None = False
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    description: str | None = None
    features: list[str] | None = []
    data_source: str | None = None
    source_id: str | None = None


class PropertyUpdate(BaseModel):
    """Property update schema"""

    price: int | None = Field(None, ge=0)
    deposit: int | None = Field(None, ge=0)
    monthly_rent: int | None = Field(None, ge=0)
    maintenance_fee: int | None = Field(None, ge=0)
    description: str | None = None
    features: list[str] | None = None
    is_active: bool | None = None


class PropertyResponse(PropertyBase, TimestampMixin):
    """Property response schema"""

    id: uuid.UUID
    building_name: str | None = None
    room_count: int | None = None
    bathroom_count: int | None = None
    area_pyeong: float | None = None
    building_year: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    deposit: int | None = None
    monthly_rent: int | None = None
    maintenance_fee: int | None = None
    transaction_date: datetime | None = None
    parking_available: bool = False
    elevator_available: bool = False
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    features: list[str] | None = []
    is_active: bool = True

    @field_validator("area_pyeong", mode="before")
    @classmethod
    def calculate_area_pyeong(cls, v):
        # For now, just return the value as is
        # TODO: Implement area calculation using model_validator if needed
        return v


class PropertySearchResult(BaseModel):
    """Property search result with relevance score"""

    property: PropertyResponse
    relevance_score: float = Field(
        ..., ge=0, le=1, description="Relevance score from vector search"
    )
    distance_km: float | None = Field(None, description="Distance from search center in km")
    matching_criteria: list[str] = Field(default=[], description="List of matching search criteria")


class PropertyStats(BaseModel):
    """Property statistics"""

    total_count: int
    average_price: float
    median_price: float
    min_price: int
    max_price: int
    price_per_m2: float
    price_per_pyeong: float
    area_distribution: dict[str, int]
    transaction_type_distribution: dict[str, int]
    property_type_distribution: dict[str, int]
