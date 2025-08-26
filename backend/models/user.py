"""
User models for Korean Real Estate RAG AI Chatbot
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, BaseSchema, TimestampMixin


class UserStatus(str, Enum):
    """User account status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class ConversationStatus(str, Enum):
    """Conversation status"""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class User(Base):
    """User database model"""

    __tablename__ = "users"

    # Basic user information
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True)
    phone_number = Column(String(20), unique=True, index=True)

    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255))

    # User status
    status = Column(String(20), default=UserStatus.ACTIVE, index=True)
    last_login = Column(DateTime)
    login_count = Column(Integer, default=0)

    # Profile information
    full_name = Column(String(200))
    birth_date = Column(DateTime)
    gender = Column(String(10))

    # Preferences
    preferred_language = Column(String(10), default="ko")
    notification_enabled = Column(Boolean, default=True)
    marketing_consent = Column(Boolean, default=False)

    # Privacy settings
    privacy_level = Column(String(20), default="standard")  # strict, standard, open
    data_retention_days = Column(Integer, default=365)

    # Relationships
    profiles = relationship("UserProfile", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship(
        "ConversationHistory", back_populates="user", cascade="all, delete-orphan"
    )


class UserProfile(Base):
    """User profile for personalized recommendations"""

    __tablename__ = "user_profiles"

    # Foreign key
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Profile information
    profile_name = Column(String(100), default="기본 프로필")
    is_primary = Column(Boolean, default=True)

    # Demographic information
    age = Column(Integer)
    annual_income = Column(Integer)  # 연봉 (원)
    household_size = Column(Integer)  # 가구 구성원 수
    marital_status = Column(String(20))  # 결혼 상태

    # Employment information
    employment_status = Column(String(50))  # 직업 상태
    job_title = Column(String(100))  # 직책
    company_type = Column(String(100))  # 회사 유형

    # Housing information
    current_residence_type = Column(String(50))  # 현재 거주 형태
    current_residence_area = Column(String(200))  # 현재 거주 지역
    is_first_time_buyer = Column(Boolean, default=True)  # 생애 최초 구매자
    previous_property_count = Column(Integer, default=0)  # 기존 보유 부동산 수

    # Financial information
    available_budget = Column(Integer)  # 가용 예산
    loan_limit = Column(Integer)  # 대출 한도
    current_debt = Column(Integer)  # 기존 부채
    savings_amount = Column(Integer)  # 저축액

    # Property preferences
    preferred_locations = Column(JSON)  # 선호 지역 리스트
    preferred_property_types = Column(JSON)  # 선호 부동산 유형
    preferred_transaction_types = Column(JSON)  # 선호 거래 유형
    min_area_requirement = Column(Float)  # 최소 면적 요구사항
    max_budget = Column(Integer)  # 최대 예산

    # Lifestyle preferences
    commute_locations = Column(JSON)  # 출퇴근 위치
    preferred_transportation = Column(JSON)  # 선호 교통수단
    school_district_important = Column(Boolean, default=False)  # 학군 중요도
    nearby_facilities = Column(JSON)  # 주변 시설 선호도

    # Policy eligibility
    eligible_policies = Column(JSON)  # 적용 가능한 정책 리스트
    policy_preferences = Column(JSON)  # 정책 선호도

    # Search history and preferences
    search_history = Column(JSON)  # 검색 이력
    favorite_properties = Column(JSON)  # 관심 매물
    preference_weights = Column(JSON)  # 선호도 가중치

    # AI model personalization
    interaction_patterns = Column(JSON)  # 상호작용 패턴
    response_preferences = Column(JSON)  # 응답 선호도

    # Relationships
    user = relationship("User", back_populates="profiles")


class ConversationHistory(Base):
    """Conversation history for chat context"""

    __tablename__ = "conversation_history"

    # Foreign key
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Conversation metadata
    conversation_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), index=True)
    title = Column(String(200))
    status = Column(String(20), default=ConversationStatus.ACTIVE)

    # Message information
    message_index = Column(Integer, nullable=False)  # Message order in conversation
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # AI processing information
    intent = Column(String(50))  # Classified intent
    entities = Column(JSON)  # Extracted entities
    context = Column(JSON)  # Additional context

    # Response metadata
    response_time_ms = Column(Integer)  # Response generation time
    model_used = Column(String(100))  # AI model used
    confidence_score = Column(Float)  # Response confidence

    # User feedback
    user_rating = Column(Integer)  # 1-5 rating
    user_feedback = Column(Text)
    was_helpful = Column(Boolean)

    # Search and recommendation data
    search_query = Column(Text)
    search_results = Column(JSON)  # Search result IDs
    recommended_properties = Column(JSON)  # Recommended property IDs
    recommended_policies = Column(JSON)  # Recommended policy IDs

    # Relationships
    user = relationship("User", back_populates="conversations")


# Pydantic schemas
class UserBase(BaseSchema):
    """Base user schema"""

    email: EmailStr = Field(..., description="User email address")
    username: str | None = Field(None, min_length=3, max_length=100, description="Username")
    phone_number: str | None = Field(
        None, pattern=r"^01[0-9]-[0-9]{4}-[0-9]{4}$", description="Phone number"
    )
    full_name: str | None = Field(None, max_length=200, description="Full name")
    preferred_language: str = Field("ko", description="Preferred language")


class UserCreate(UserBase):
    """User creation schema"""

    password: str = Field(..., min_length=8, max_length=100, description="Password")
    birth_date: datetime | None = None
    gender: str | None = Field(None, pattern=r"^(male|female|other)$")
    marketing_consent: bool = False


class UserUpdate(BaseModel):
    """User update schema"""

    username: str | None = Field(None, min_length=3, max_length=100)
    phone_number: str | None = Field(None, pattern=r"^01[0-9]-[0-9]{4}-[0-9]{4}$")
    full_name: str | None = Field(None, max_length=200)
    preferred_language: str | None = None
    notification_enabled: bool | None = None
    marketing_consent: bool | None = None


class UserResponse(UserBase, TimestampMixin):
    """User response schema"""

    id: uuid.UUID
    status: UserStatus
    is_verified: bool
    last_login: datetime | None = None
    login_count: int


class UserProfileBase(BaseSchema):
    """Base user profile schema"""

    profile_name: str = Field("기본 프로필", max_length=100)
    age: int | None = Field(None, ge=18, le=100)
    annual_income: int | None = Field(None, ge=0)
    household_size: int | None = Field(None, ge=1, le=20)
    max_budget: int | None = Field(None, ge=0)


class UserProfileCreate(UserProfileBase):
    """User profile creation schema"""

    marital_status: str | None = None
    employment_status: str | None = None
    current_residence_type: str | None = None
    current_residence_area: str | None = None
    is_first_time_buyer: bool = True
    available_budget: int | None = Field(None, ge=0)
    preferred_locations: list[str] | None = []
    preferred_property_types: list[str] | None = []
    preferred_transaction_types: list[str] | None = []


class UserProfileUpdate(BaseModel):
    """User profile update schema"""

    profile_name: str | None = Field(None, max_length=100)
    age: int | None = Field(None, ge=18, le=100)
    annual_income: int | None = Field(None, ge=0)
    max_budget: int | None = Field(None, ge=0)
    preferred_locations: list[str] | None = None
    preferred_property_types: list[str] | None = None


class UserProfileResponse(UserProfileBase, TimestampMixin):
    """User profile response schema"""

    id: uuid.UUID
    user_id: uuid.UUID
    is_primary: bool
    marital_status: str | None = None
    employment_status: str | None = None
    is_first_time_buyer: bool
    preferred_locations: list[str] | None = []
    preferred_property_types: list[str] | None = []
    eligible_policies: list[str] | None = []


class ConversationCreate(BaseModel):
    """Conversation creation schema"""

    conversation_id: str = Field(..., max_length=100)
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    intent: str | None = None
    entities: dict[str, Any] | None = None


class ConversationResponse(BaseSchema, TimestampMixin):
    """Conversation response schema"""

    id: uuid.UUID
    conversation_id: str
    message_index: int
    role: str
    content: str
    intent: str | None = None
    confidence_score: float | None = None
    user_rating: int | None = None
    was_helpful: bool | None = None


class UserStats(BaseModel):
    """User statistics"""

    total_conversations: int
    total_messages: int
    average_session_duration: float
    favorite_property_types: list[str]
    most_searched_locations: list[str]
    interaction_frequency: dict[str, int]
