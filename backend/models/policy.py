"""
Government policy models for Korean Real Estate support
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, BaseSchema, TimestampMixin


class PolicyType(str, Enum):
    """Government policy types"""
    YOUTH_HOUSING = "청년주택"
    NEWLYWED_SUPPORT = "신혼부부지원"
    FIRST_TIME_BUYER = "생애최초구매"
    JEONSE_LOAN = "전세대출"
    PURCHASE_LOAN = "구매대출"
    SPECIAL_SUPPLY = "특별공급"
    PUBLIC_RENTAL = "공공임대"
    GUARANTEE_INSURANCE = "보증보험"


class PolicyStatus(str, Enum):
    """Policy status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    PENDING = "pending"


class EligibilityRequirement(str, Enum):
    """Eligibility requirement types"""
    AGE = "age"
    INCOME = "income"
    HOUSEHOLD_SIZE = "household_size"
    MARITAL_STATUS = "marital_status"
    FIRST_TIME_BUYER = "first_time_buyer"
    RESIDENCE_AREA = "residence_area"
    EMPLOYMENT_STATUS = "employment_status"
    SAVINGS_AMOUNT = "savings_amount"


class GovernmentPolicy(Base):
    """Government policy database model"""
    __tablename__ = "government_policies"
    
    # Basic policy information
    policy_name = Column(String(200), nullable=False, index=True)
    policy_code = Column(String(50), unique=True, index=True)
    policy_type = Column(String(50), nullable=False, index=True)
    policy_category = Column(String(100), index=True)
    
    # Organizing institution
    organizing_institution = Column(String(200), nullable=False)  # 주관 기관
    contact_info = Column(JSON)  # 연락처 정보
    website_url = Column(String(500))
    
    # Policy details
    description = Column(Text, nullable=False)
    summary = Column(Text)
    benefits = Column(JSON)  # 혜택 내용
    application_process = Column(JSON)  # 신청 절차
    required_documents = Column(JSON)  # 필요 서류
    
    # Eligibility criteria
    eligibility_requirements = Column(JSON, nullable=False)  # 자격 요건
    income_criteria = Column(JSON)  # 소득 기준
    age_criteria = Column(JSON)  # 나이 기준
    area_restrictions = Column(JSON)  # 지역 제한
    
    # Financial information
    loan_limit = Column(Integer)  # 대출 한도
    interest_rate = Column(Float)  # 금리
    loan_to_value_ratio = Column(Float)  # LTV 비율
    debt_to_income_ratio = Column(Float)  # DTI 비율
    guarantee_fee_rate = Column(Float)  # 보증료율
    
    # Application information
    application_period_start = Column(DateTime)  # 신청 기간 시작
    application_period_end = Column(DateTime)  # 신청 기간 종료
    application_method = Column(String(100))  # 신청 방법
    selection_method = Column(String(200))  # 선정 방법
    
    # Status and validity
    status = Column(String(20), default=PolicyStatus.ACTIVE, index=True)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Additional information
    target_group = Column(String(200))  # 대상자
    special_conditions = Column(JSON)  # 특별 조건
    related_policies = Column(JSON)  # 연관 정책
    faq = Column(JSON)  # 자주 묻는 질문
    
    # Statistics
    application_count = Column(Integer, default=0)  # 신청 건수
    approval_count = Column(Integer, default=0)  # 승인 건수
    approval_rate = Column(Float)  # 승인률
    
    # Search optimization
    search_keywords = Column(JSON)  # 검색 키워드
    search_vector = Column(Text)  # 벡터 임베딩 ID


class PolicyMatch(Base):
    """User-Policy matching results"""
    __tablename__ = "policy_matches"
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    policy_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Matching information
    match_score = Column(Float, nullable=False)  # 매칭 점수 (0-1)
    eligibility_status = Column(String(20), nullable=False)  # eligible, partial, not_eligible
    
    # Detailed matching analysis
    met_requirements = Column(JSON)  # 충족된 요건
    unmet_requirements = Column(JSON)  # 미충족 요건
    required_actions = Column(JSON)  # 필요한 조치
    
    # Financial analysis
    estimated_loan_amount = Column(Integer)  # 예상 대출 가능 금액
    estimated_interest_rate = Column(Float)  # 예상 금리
    estimated_monthly_payment = Column(Integer)  # 예상 월 상환액
    
    # Application information
    application_deadline = Column(DateTime)  # 신청 마감일
    application_priority = Column(Integer)  # 신청 우선순위 (1-5)
    
    # User interaction
    user_interest_level = Column(Integer)  # 사용자 관심도 (1-5)
    is_bookmarked = Column(Boolean, default=False)
    application_status = Column(String(50))  # 신청 상태
    
    # Match timestamp
    matched_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)


# Pydantic schemas
class PolicyBase(BaseSchema):
    """Base policy schema"""
    policy_name: str = Field(..., max_length=200, description="Policy name")
    policy_code: str = Field(..., max_length=50, description="Policy code")
    policy_type: PolicyType = Field(..., description="Policy type")
    organizing_institution: str = Field(..., description="Organizing institution")
    description: str = Field(..., description="Policy description")


class PolicyCreate(PolicyBase):
    """Policy creation schema"""
    policy_category: str | None = None
    summary: str | None = None
    benefits: dict[str, Any] | None = None
    eligibility_requirements: dict[str, Any] = Field(..., description="Eligibility requirements")
    income_criteria: dict[str, Any] | None = None
    age_criteria: dict[str, Any] | None = None
    area_restrictions: list[str] | None = None
    loan_limit: int | None = Field(None, ge=0)
    interest_rate: float | None = Field(None, ge=0, le=100)
    effective_date: datetime = Field(..., description="Effective date")
    expiry_date: datetime | None = None
    target_group: str | None = None
    application_method: str | None = None
    website_url: str | None = None


class PolicyUpdate(BaseModel):
    """Policy update schema"""
    policy_name: str | None = Field(None, max_length=200)
    description: str | None = None
    status: PolicyStatus | None = None
    loan_limit: int | None = Field(None, ge=0)
    interest_rate: float | None = Field(None, ge=0, le=100)
    expiry_date: datetime | None = None
    eligibility_requirements: dict[str, Any] | None = None


class PolicyResponse(PolicyBase, TimestampMixin):
    """Policy response schema"""
    id: uuid.UUID
    policy_category: str | None = None
    summary: str | None = None
    benefits: dict[str, Any] | None = None
    eligibility_requirements: dict[str, Any]
    income_criteria: dict[str, Any] | None = None
    age_criteria: dict[str, Any] | None = None
    area_restrictions: list[str] | None = None
    loan_limit: int | None = None
    interest_rate: float | None = None
    status: PolicyStatus
    effective_date: datetime
    expiry_date: datetime | None = None
    target_group: str | None = None
    website_url: str | None = None
    approval_rate: float | None = None


class PolicyMatchBase(BaseSchema):
    """Base policy match schema"""
    policy_id: uuid.UUID = Field(..., description="Policy ID")
    match_score: float = Field(..., ge=0, le=1, description="Match score")
    eligibility_status: str = Field(..., description="Eligibility status")


class PolicyMatchCreate(PolicyMatchBase):
    """Policy match creation schema"""
    user_id: uuid.UUID = Field(..., description="User ID")
    met_requirements: list[str] | None = []
    unmet_requirements: list[str] | None = []
    required_actions: list[str] | None = []
    estimated_loan_amount: int | None = Field(None, ge=0)
    estimated_interest_rate: float | None = Field(None, ge=0)
    application_deadline: datetime | None = None
    application_priority: int = Field(3, ge=1, le=5)


class PolicyMatchResponse(PolicyMatchBase, TimestampMixin):
    """Policy match response schema"""
    id: uuid.UUID
    user_id: uuid.UUID
    policy: PolicyResponse
    met_requirements: list[str] | None = []
    unmet_requirements: list[str] | None = []
    required_actions: list[str] | None = []
    estimated_loan_amount: int | None = None
    estimated_interest_rate: float | None = None
    estimated_monthly_payment: int | None = None
    application_deadline: datetime | None = None
    application_priority: int
    user_interest_level: int | None = None
    is_bookmarked: bool = False
    matched_at: datetime


class PolicyFilter(BaseModel):
    """Policy search filter"""
    policy_types: list[PolicyType] | None = None
    organizing_institutions: list[str] | None = None
    status: list[PolicyStatus] | None = None
    target_groups: list[str] | None = None
    min_loan_limit: int | None = None
    max_interest_rate: float | None = None
    area_restrictions: list[str] | None = None
    effective_date_from: datetime | None = None
    effective_date_to: datetime | None = None
    search_keyword: str | None = None


class PolicyRecommendation(BaseModel):
    """Policy recommendation result"""
    policy: PolicyResponse
    match_score: float = Field(..., ge=0, le=1)
    eligibility_status: str
    recommendation_reason: str
    estimated_benefits: dict[str, Any]
    next_steps: list[str]


class PolicyStats(BaseModel):
    """Policy statistics"""
    total_policies: int
    active_policies: int
    policy_type_distribution: dict[str, int]
    average_approval_rate: float
    most_popular_policies: list[str]
    recent_policy_updates: list[str]