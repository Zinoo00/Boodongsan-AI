-- Migration: Properties Schema
-- Description: Create properties table for Korean real estate listings
-- Author: BODA Development Team
-- Date: 2025-01-23
-- Dependencies: None

-- ==============================================================================
-- Properties Table
-- ==============================================================================
-- Stores Korean real estate property listings
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 주소 정보 (Address Information)
    address TEXT NOT NULL,
    district VARCHAR(50),  -- 구 (예: 강남구, 서초구)
    dong VARCHAR(50),      -- 동 (예: 역삼동, 서초동)
    detail_address VARCHAR(200),  -- 상세 주소

    -- 부동산 유형 (Property Type)
    property_type VARCHAR(30) NOT NULL,  -- 아파트, 오피스텔, 빌라, 단독주택, 상가, 토지
    transaction_type VARCHAR(20) NOT NULL,  -- 매매, 전세, 월세, 단기임대

    -- 가격 정보 (Price Information)
    price BIGINT,  -- 매매가 또는 전세 보증금 (원 단위)
    deposit BIGINT,  -- 보증금 (월세인 경우)
    monthly_rent BIGINT,  -- 월세 (월세인 경우)
    maintenance_fee BIGINT,  -- 관리비

    -- 면적 정보 (Area Information)
    area_exclusive DECIMAL(10, 2),  -- 전용면적 (m²)
    area_supply DECIMAL(10, 2),  -- 공급면적 (m²)
    area_land DECIMAL(10, 2),  -- 대지면적 (단독주택/토지)
    area_pyeong DECIMAL(10, 2),  -- 평수 (환산값)

    -- 건물 정보 (Building Information)
    room_count INTEGER DEFAULT 0,  -- 방 개수
    bathroom_count INTEGER DEFAULT 0,  -- 욕실 개수
    floor INTEGER,  -- 층
    total_floors INTEGER,  -- 전체 층수
    building_year INTEGER,  -- 건축 연도
    parking_available BOOLEAN DEFAULT false,  -- 주차 가능 여부
    parking_count INTEGER,  -- 주차 대수

    -- 위치 정보 (Location Information)
    latitude DECIMAL(10, 7),  -- 위도
    longitude DECIMAL(10, 7),  -- 경도

    -- 상세 정보 (Detailed Information)
    description TEXT,  -- 상세 설명
    amenities TEXT[],  -- 편의시설 배열 (예: ['엘리베이터', '인터폰', '난방'])
    nearby_facilities JSONB DEFAULT '{}',  -- 주변 시설 (학교, 지하철역, 공원 등)
    -- Example: {"schools": ["역삼초등학교"], "subway": ["역삼역"], "hospitals": ["강남병원"]}

    -- 매물 특성 (Listing Characteristics)
    is_new_building BOOLEAN DEFAULT false,  -- 신축 여부
    is_remodeled BOOLEAN DEFAULT false,  -- 리모델링 여부
    move_in_date DATE,  -- 입주 가능일
    direction VARCHAR(10),  -- 향 (남향, 동향 등)
    heating_type VARCHAR(20),  -- 난방 방식 (개별난방, 중앙난방 등)

    -- 중개 정보 (Brokerage Information)
    broker_name VARCHAR(100),  -- 중개사 이름
    broker_contact VARCHAR(20),  -- 중개사 연락처

    -- 메타데이터 (Metadata)
    source VARCHAR(50) DEFAULT 'user_input',  -- 데이터 출처 (molit, zigbang, user_input 등)
    source_id VARCHAR(100),  -- 원본 데이터 ID
    listing_status VARCHAR(20) DEFAULT 'active',  -- active, sold, expired, pending
    view_count INTEGER DEFAULT 0,  -- 조회수
    favorite_count INTEGER DEFAULT 0,  -- 찜 개수

    -- 타임스탬프 (Timestamps)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- 매물 만료일

    -- 제약 조건 (Constraints)
    CONSTRAINT valid_property_type CHECK (property_type IN (
        '아파트', '오피스텔', '빌라', '단독주택', '다세대', '상가', '토지', '기타'
    )),
    CONSTRAINT valid_transaction_type CHECK (transaction_type IN (
        '매매', '전세', '월세', '단기임대'
    )),
    CONSTRAINT valid_listing_status CHECK (listing_status IN (
        'active', 'sold', 'expired', 'pending', 'hidden'
    )),
    CONSTRAINT valid_price CHECK (
        (transaction_type = '매매' AND price IS NOT NULL) OR
        (transaction_type = '전세' AND price IS NOT NULL) OR
        (transaction_type = '월세' AND deposit IS NOT NULL AND monthly_rent IS NOT NULL)
    )
);

-- ==============================================================================
-- Indexes for Performance
-- ==============================================================================

-- 위치 기반 검색
CREATE INDEX idx_properties_location ON properties(district, dong);
CREATE INDEX idx_properties_coordinates ON properties(latitude, longitude);

-- 유형 기반 검색
CREATE INDEX idx_properties_type ON properties(property_type, transaction_type);

-- 가격 범위 검색
CREATE INDEX idx_properties_price ON properties(price) WHERE price IS NOT NULL;
CREATE INDEX idx_properties_rent ON properties(monthly_rent) WHERE monthly_rent IS NOT NULL;

-- 면적 범위 검색
CREATE INDEX idx_properties_area ON properties(area_exclusive) WHERE area_exclusive IS NOT NULL;

-- 상태 및 정렬
CREATE INDEX idx_properties_status ON properties(listing_status);
CREATE INDEX idx_properties_created ON properties(created_at DESC);
CREATE INDEX idx_properties_updated ON properties(updated_at DESC);

-- JSONB 검색 (주변 시설)
CREATE INDEX idx_properties_nearby ON properties USING GIN (nearby_facilities);

-- 복합 인덱스 (자주 사용되는 필터 조합)
CREATE INDEX idx_properties_active_location ON properties(listing_status, district, dong)
    WHERE listing_status = 'active';

CREATE INDEX idx_properties_active_type_price ON properties(listing_status, property_type, price)
    WHERE listing_status = 'active';

-- ==============================================================================
-- Triggers
-- ==============================================================================

-- 자동 updated_at 업데이트
CREATE OR REPLACE FUNCTION update_properties_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER properties_updated_at_trigger
    BEFORE UPDATE ON properties
    FOR EACH ROW
    EXECUTE FUNCTION update_properties_updated_at();

-- 평수 자동 계산 (전용면적 기준)
CREATE OR REPLACE FUNCTION calculate_area_pyeong()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.area_exclusive IS NOT NULL THEN
        NEW.area_pyeong = ROUND((NEW.area_exclusive / 3.305785)::numeric, 2);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER properties_calculate_pyeong_trigger
    BEFORE INSERT OR UPDATE OF area_exclusive ON properties
    FOR EACH ROW
    EXECUTE FUNCTION calculate_area_pyeong();

-- ==============================================================================
-- Comments
-- ==============================================================================

COMMENT ON TABLE properties IS 'Korean real estate property listings';
COMMENT ON COLUMN properties.district IS '구 단위 행정구역 (예: 강남구)';
COMMENT ON COLUMN properties.dong IS '동 단위 행정구역 (예: 역삼동)';
COMMENT ON COLUMN properties.property_type IS '부동산 유형: 아파트, 오피스텔, 빌라, 단독주택, 다세대, 상가, 토지, 기타';
COMMENT ON COLUMN properties.transaction_type IS '거래 유형: 매매, 전세, 월세, 단기임대';
COMMENT ON COLUMN properties.price IS '매매가 또는 전세 보증금 (원)';
COMMENT ON COLUMN properties.area_exclusive IS '전용면적 (㎡)';
COMMENT ON COLUMN properties.area_pyeong IS '평수 (전용면적 기준 자동 계산)';
COMMENT ON COLUMN properties.nearby_facilities IS 'JSONB 형식의 주변 시설 정보';
COMMENT ON COLUMN properties.listing_status IS '매물 상태: active, sold, expired, pending, hidden';

-- ==============================================================================
-- Sample Data (Optional - for testing)
-- ==============================================================================

-- Uncomment to insert sample data for testing
/*
INSERT INTO properties (
    address, district, dong, property_type, transaction_type,
    price, area_exclusive, room_count, building_year,
    description, listing_status
) VALUES
    (
        '서울특별시 강남구 역삼동 123',
        '강남구', '역삼동', '아파트', '전세',
        500000000, 84.32, 3, 2018,
        '강남역 5분거리 신축 아파트, 역세권, 학군 우수',
        'active'
    ),
    (
        '서울특별시 서초구 서초동 456',
        '서초구', '서초동', '오피스텔', '월세',
        50000000, 33.12, 1, 2020,
        '서초역 역세권 오피스텔, 풀옵션, 보안 철저',
        'active'
    ),
    (
        '서울특별시 송파구 잠실동 789',
        '송파구', '잠실동', '아파트', '매매',
        1200000000, 114.32, 4, 2015,
        '잠실 롯데월드타워 전망 아파트, 초등학교 도보 3분',
        'active'
    );
*/
