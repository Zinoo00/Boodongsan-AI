"""
SQLAlchemy 데이터베이스 모델 정의
"""

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Text, DECIMAL, ARRAY, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """사용자 기본 정보"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    annual_income = Column(BigInteger, nullable=False)  # 연봉 (원)
    job_type = Column(String(50))
    marital_status = Column(String(20))
    dependents = Column(Integer, default=0)  # 부양가족 수
    region_preference = Column(String(100))  # 선호 지역
    budget_min = Column(BigInteger)  # 최소 예산
    budget_max = Column(BigInteger)  # 최대 예산
    
    # 특별 조건
    is_first_time_buyer = Column(Boolean, default=True)  # 생애최초 구입자
    is_newlywed = Column(Boolean, default=False)  # 신혼부부
    has_multiple_children = Column(Boolean, default=False)  # 다자녀 가구
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    preferences = relationship("UserPreference", back_populates="user")
    conversations = relationship("ConversationHistory", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, age={self.age})>"

class UserPreference(Base):
    """사용자 부동산 선호도"""
    __tablename__ = "user_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    property_type = Column(String(50))  # 아파트, 빌라, 단독주택 등
    room_count = Column(Integer)
    area_min = Column(Integer)  # 최소 면적 (평)
    area_max = Column(Integer)  # 최대 면적 (평)
    
    # 중요도 점수 (1-5)
    transportation_importance = Column(Integer, default=3)
    school_district_importance = Column(Integer, default=3)
    amenities_importance = Column(Integer, default=3)
    security_importance = Column(Integer, default=3)
    parking_importance = Column(Integer, default=3)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    user = relationship("User", back_populates="preferences")
    
    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id}, property_type={self.property_type})>"

class Property(Base):
    """부동산 매물 정보"""
    __tablename__ = "properties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    property_type = Column(String(50), nullable=False)  # 아파트, 빌라, 오피스텔 등
    transaction_type = Column(String(20), nullable=False)  # 매매, 전세, 월세
    
    # 주소 정보
    address = Column(String(300), nullable=False)
    district = Column(String(100), nullable=False)  # 구
    dong = Column(String(100), nullable=False)  # 동
    detail_address = Column(String(200))  # 상세 주소
    
    # 가격 정보
    price = Column(BigInteger, nullable=False)  # 매매가 또는 전세가
    monthly_rent = Column(BigInteger, default=0)  # 월세
    deposit = Column(BigInteger, default=0)  # 보증금
    maintenance_cost = Column(Integer, default=0)  # 관리비
    
    # 면적 정보
    area_exclusive = Column(DECIMAL(8, 2))  # 전용면적 (㎡)
    area_supply = Column(DECIMAL(8, 2))  # 공급면적 (㎡)
    area_pyeong = Column(DECIMAL(8, 2))  # 평수
    
    # 건물 정보
    floor_current = Column(Integer)  # 현재 층수
    floor_total = Column(Integer)  # 전체 층수
    year_built = Column(Integer)  # 건축년도
    room_count = Column(Integer)  # 방 개수
    bathroom_count = Column(Integer)  # 화장실 개수
    
    # 편의시설
    parking_available = Column(Boolean, default=False)
    elevator_available = Column(Boolean, default=False)
    balcony_available = Column(Boolean, default=False)
    
    # 지리적 정보
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    
    # 교통 정보
    nearest_subway = Column(String(100))
    subway_distance = Column(Integer)  # 미터 단위
    bus_stops_nearby = Column(Integer, default=0)
    
    # 학군 정보
    elementary_school = Column(String(100))
    middle_school = Column(String(100))
    high_school = Column(String(100))
    
    # 기타 정보
    description = Column(Text)
    image_urls = Column(ARRAY(String))  # 이미지 URL 배열
    contact_info = Column(String(200))  # 연락처
    
    # 상태
    is_available = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # 추천 매물
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    amenities = relationship("PropertyAmenity", back_populates="property")
    
    # 인덱스
    __table_args__ = (
        Index('idx_property_district_dong', 'district', 'dong'),
        Index('idx_property_type_transaction', 'property_type', 'transaction_type'),
        Index('idx_property_price_range', 'price'),
        Index('idx_property_area_range', 'area_exclusive'),
        Index('idx_property_location', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<Property(id={self.id}, title={self.title}, district={self.district})>"

class PropertyAmenity(Base):
    """부동산 편의시설 정보"""
    __tablename__ = "property_amenities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    
    amenity_type = Column(String(50), nullable=False)  # 마트, 병원, 공원 등
    name = Column(String(100), nullable=False)
    distance = Column(Integer, nullable=False)  # 미터 단위
    rating = Column(DECIMAL(3, 2))  # 별점 (0.00 ~ 5.00)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    property = relationship("Property", back_populates="amenities")
    
    def __repr__(self):
        return f"<PropertyAmenity(property_id={self.property_id}, type={self.amenity_type})>"

class GovernmentPolicy(Base):
    """정부 지원 정책 마스터"""
    __tablename__ = "government_policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_name = Column(String(200), nullable=False)
    policy_type = Column(String(50), nullable=False)  # 전세자금, 구입자금, 임대주택 등
    policy_category = Column(String(50))  # 청년, 신혼부부, 다자녀 등
    description = Column(Text)
    
    # 자격 조건
    age_min = Column(Integer)
    age_max = Column(Integer)
    income_min = Column(BigInteger)
    income_max = Column(BigInteger)
    asset_limit = Column(BigInteger)  # 자산 한도
    
    # 혜택 내용
    loan_limit = Column(BigInteger)  # 대출 한도
    interest_rate = Column(DECIMAL(5, 2))  # 금리
    loan_period_max = Column(Integer)  # 최대 대출 기간 (년)
    
    # 지역 제한
    available_regions = Column(ARRAY(String))  # 적용 가능 지역
    excluded_regions = Column(ARRAY(String))  # 제외 지역
    
    # 특별 조건
    first_time_buyer_only = Column(Boolean, default=False)
    newlywed_priority = Column(Boolean, default=False)
    multi_child_benefit = Column(Boolean, default=False)
    
    # 신청 정보
    application_url = Column(String(500))  # 신청 URL
    required_documents = Column(ARRAY(String))  # 필요 서류
    contact_info = Column(String(300))  # 문의처
    
    # 상태
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    conditions = relationship("PolicyCondition", back_populates="policy")
    
    def __repr__(self):
        return f"<GovernmentPolicy(id={self.id}, name={self.policy_name})>"

class PolicyCondition(Base):
    """정책별 세부 조건"""
    __tablename__ = "policy_conditions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("government_policies.id"), nullable=False)
    
    condition_type = Column(String(50), nullable=False)  # 소득, 자산, 지역, 기타
    condition_key = Column(String(100), nullable=False)
    condition_value = Column(Text, nullable=False)
    condition_operator = Column(String(10), nullable=False)  # >=, <=, =, IN 등
    
    description = Column(String(500))  # 조건 설명
    is_required = Column(Boolean, default=True)  # 필수 조건 여부
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    policy = relationship("GovernmentPolicy", back_populates="conditions")
    
    def __repr__(self):
        return f"<PolicyCondition(policy_id={self.policy_id}, type={self.condition_type})>"

class ConversationHistory(Base):
    """대화 이력"""
    __tablename__ = "conversation_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(100), nullable=False)
    
    # 메시지 정보
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    
    # 추출된 정보
    extracted_entities = Column(JSONB)  # JSON 형태로 저장
    detected_intent = Column(String(50))
    
    # 추천 결과
    recommended_policies = Column(ARRAY(String))  # 정책 ID 배열
    recommended_properties = Column(ARRAY(String))  # 매물 ID 배열
    
    # 메타데이터
    processing_time = Column(Integer)  # 처리 시간 (ms)
    confidence_score = Column(DECIMAL(5, 4))  # 신뢰도 점수
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    user = relationship("User", back_populates="conversations")
    
    # 인덱스
    __table_args__ = (
        Index('idx_conversation_user_session', 'user_id', 'session_id'),
        Index('idx_conversation_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ConversationHistory(user_id={self.user_id}, session_id={self.session_id})>"

class UserPropertyMatch(Base):
    """사용자-부동산 매칭 점수"""
    __tablename__ = "user_property_matches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    
    # 매칭 점수
    overall_score = Column(DECIMAL(5, 4), nullable=False)  # 전체 점수 (0.0000 ~ 1.0000)
    price_score = Column(DECIMAL(5, 4))  # 가격 매칭 점수
    location_score = Column(DECIMAL(5, 4))  # 위치 매칭 점수
    amenity_score = Column(DECIMAL(5, 4))  # 편의시설 점수
    preference_score = Column(DECIMAL(5, 4))  # 선호도 점수
    
    # 매칭 사유
    match_reasons = Column(ARRAY(String))  # 매칭 이유들
    mismatch_reasons = Column(ARRAY(String))  # 불일치 이유들
    
    # 메타데이터
    calculated_at = Column(DateTime, default=datetime.utcnow)
    is_recommended = Column(Boolean, default=False)  # 추천 여부
    
    # 인덱스
    __table_args__ = (
        Index('idx_user_property_score', 'user_id', 'overall_score'),
        Index('idx_property_user_score', 'property_id', 'overall_score'),
    )
    
    def __repr__(self):
        return f"<UserPropertyMatch(user_id={self.user_id}, property_id={self.property_id}, score={self.overall_score})>"