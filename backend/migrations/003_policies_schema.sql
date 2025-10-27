-- Migration: Government Policies Schema
-- Description: Create government housing policies table
-- Author: BODA Development Team
-- Date: 2025-01-23
-- Dependencies: None

-- ==============================================================================
-- Government Policies Table
-- ==============================================================================
-- Stores Korean government housing support policies
CREATE TABLE IF NOT EXISTS government_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 정책 기본 정보 (Policy Basic Information)
    policy_name VARCHAR(200) NOT NULL,  -- 정책명 (한글)
    policy_name_english VARCHAR(200),  -- 정책명 (영문)
    policy_code VARCHAR(50) UNIQUE,  -- 정책 코드 (고유 식별자)
    policy_type VARCHAR(50) NOT NULL,  -- 정책 유형
    category VARCHAR(50),  -- 카테고리

    -- 설명 (Description)
    description TEXT,  -- 상세 설명
    summary TEXT NOT NULL,  -- 간단한 요약 (필수)
    benefits TEXT,  -- 지원 혜택
    support_details JSONB DEFAULT '{}',  -- 지원 내용 상세

    -- 대상 (Target Audience)
    target_demographic VARCHAR(100),  -- 대상 인구통계 (청년, 신혼부부, 다자녀, 저소득층 등)
    target_description TEXT,  -- 대상 설명

    -- 연령 조건 (Age Requirements)
    age_min INTEGER,  -- 최소 연령
    age_max INTEGER,  -- 최대 연령

    -- 소득 조건 (Income Requirements)
    income_min BIGINT,  -- 최소 연소득 (원)
    income_max BIGINT,  -- 최대 연소득 (원)
    income_percentile INTEGER,  -- 소득 분위 (예: 70% 이하)

    -- 자산 조건 (Asset Requirements)
    asset_max BIGINT,  -- 최대 자산 (원)
    vehicle_value_max BIGINT,  -- 최대 차량 가액 (원)

    -- 지역 조건 (Regional Requirements)
    available_regions TEXT[],  -- 적용 가능 지역 배열
    region_restriction_type VARCHAR(20),  -- 'whitelist' (지정 지역만) or 'blacklist' (제외 지역)

    -- 주택 조건 (Housing Requirements)
    property_types TEXT[],  -- 적용 가능 부동산 유형
    transaction_types TEXT[],  -- 적용 가능 거래 유형
    property_price_max BIGINT,  -- 최대 주택 가격 (원)
    property_area_max DECIMAL(10, 2),  -- 최대 주택 면적 (m²)

    -- 추가 자격 조건 (Additional Eligibility)
    requires_first_time_buyer BOOLEAN DEFAULT false,  -- 생애 최초 구입자 여부
    requires_newlywed BOOLEAN DEFAULT false,  -- 신혼부부 여부
    requires_children BOOLEAN DEFAULT false,  -- 자녀 보유 여부
    minimum_children_count INTEGER,  -- 최소 자녀 수
    requires_no_house BOOLEAN DEFAULT false,  -- 무주택자 여부

    -- 복합 조건 (Complex Requirements)
    additional_requirements JSONB DEFAULT '{}',  -- 기타 자격 요건 (유연한 구조)
    restrictions JSONB DEFAULT '{}',  -- 제한사항
    required_documents TEXT[],  -- 필요 서류 목록

    -- 신청 정보 (Application Information)
    application_period_start DATE,  -- 신청 기간 시작
    application_period_end DATE,  -- 신청 기간 종료
    is_ongoing BOOLEAN DEFAULT true,  -- 상시 접수 여부
    application_method TEXT,  -- 신청 방법
    application_url TEXT,  -- 신청 페이지 URL
    application_process TEXT,  -- 신청 절차 설명

    -- 연락처 정보 (Contact Information)
    contact_info JSONB DEFAULT '{}',  -- 연락처 정보
    -- Example: {"phone": "1234-5678", "email": "example@gov.kr", "address": "서울시 ..."}

    -- 운영 기관 (Administering Organization)
    administering_organization VARCHAR(100),  -- 운영 기관 (국토교통부, HUG, HF 등)
    department VARCHAR(100),  -- 담당 부서

    -- 지원 규모 (Support Scale)
    support_amount_min BIGINT,  -- 최소 지원 금액 (원)
    support_amount_max BIGINT,  -- 최대 지원 금액 (원)
    support_duration_months INTEGER,  -- 지원 기간 (개월)
    interest_rate DECIMAL(5, 2),  -- 이자율 (대출 정책인 경우)

    -- 메타데이터 (Metadata)
    is_active BOOLEAN DEFAULT true,  -- 활성 상태
    priority INTEGER DEFAULT 0,  -- 정렬 우선순위 (높을수록 우선)
    view_count INTEGER DEFAULT 0,  -- 조회수
    application_count INTEGER DEFAULT 0,  -- 신청 건수 (추정치)

    -- 관련 정보 (Related Information)
    related_policies UUID[],  -- 관련 정책 ID 배열
    tags TEXT[],  -- 태그 (검색 최적화용)

    -- 출처 및 참고 (Source & Reference)
    source_url TEXT,  -- 원본 정보 URL
    reference_documents TEXT[],  -- 참고 문서 목록
    legal_basis TEXT,  -- 법적 근거

    -- 타임스탬프 (Timestamps)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_verified_at TIMESTAMP,  -- 마지막 검증일

    -- 제약 조건 (Constraints)
    CONSTRAINT valid_policy_type CHECK (policy_type IN (
        '주거지원', '대출지원', '특별공급', '임대지원', '구입지원', '보증지원', '기타'
    )),
    CONSTRAINT valid_demographic CHECK (target_demographic IN (
        '청년', '신혼부부', '다자녀가구', '저소득층', '생애최초', '고령자', '장애인', '일반', '기타'
    )),
    CONSTRAINT valid_age_range CHECK (age_min IS NULL OR age_max IS NULL OR age_min <= age_max),
    CONSTRAINT valid_income_range CHECK (income_min IS NULL OR income_max IS NULL OR income_min <= income_max),
    CONSTRAINT valid_region_restriction CHECK (region_restriction_type IN ('whitelist', 'blacklist', 'none'))
);

-- ==============================================================================
-- Indexes for Performance
-- ==============================================================================

-- 정책 유형 및 상태
CREATE INDEX idx_policies_type ON government_policies(policy_type);
CREATE INDEX idx_policies_active ON government_policies(is_active);
CREATE INDEX idx_policies_priority ON government_policies(priority DESC, created_at DESC);

-- 대상자 검색
CREATE INDEX idx_policies_demographic ON government_policies(target_demographic);
CREATE INDEX idx_policies_age ON government_policies(age_min, age_max);
CREATE INDEX idx_policies_income ON government_policies(income_min, income_max);

-- 신청 기간
CREATE INDEX idx_policies_application_period ON government_policies(application_period_start, application_period_end);

-- 운영 기관
CREATE INDEX idx_policies_organization ON government_policies(administering_organization);

-- JSONB 검색
CREATE INDEX idx_policies_requirements ON government_policies USING GIN (additional_requirements);
CREATE INDEX idx_policies_contact ON government_policies USING GIN (contact_info);

-- 텍스트 검색 (정책명)
CREATE INDEX idx_policies_name ON government_policies USING gin(to_tsvector('korean', policy_name));

-- 태그 검색
CREATE INDEX idx_policies_tags ON government_policies USING GIN (tags);

-- 복합 인덱스
CREATE INDEX idx_policies_active_type ON government_policies(is_active, policy_type, target_demographic)
    WHERE is_active = true;

-- ==============================================================================
-- Triggers
-- ==============================================================================

-- 자동 updated_at 업데이트
CREATE OR REPLACE FUNCTION update_policies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER policies_updated_at_trigger
    BEFORE UPDATE ON government_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_policies_updated_at();

-- ==============================================================================
-- Helper View: Active Policies
-- ==============================================================================

CREATE OR REPLACE VIEW active_policies AS
SELECT *
FROM government_policies
WHERE is_active = true
  AND (application_period_end IS NULL OR application_period_end >= CURRENT_DATE)
ORDER BY priority DESC, created_at DESC;

-- ==============================================================================
-- Comments
-- ==============================================================================

COMMENT ON TABLE government_policies IS 'Korean government housing support policies';
COMMENT ON COLUMN government_policies.policy_type IS '정책 유형: 주거지원, 대출지원, 특별공급, 임대지원, 구입지원, 보증지원, 기타';
COMMENT ON COLUMN government_policies.target_demographic IS '대상 인구통계: 청년, 신혼부부, 다자녀가구, 저소득층, 생애최초, 고령자, 장애인, 일반, 기타';
COMMENT ON COLUMN government_policies.additional_requirements IS 'JSONB 형식의 추가 자격 요건';
COMMENT ON COLUMN government_policies.contact_info IS 'JSONB 형식의 연락처 정보';
COMMENT ON COLUMN government_policies.priority IS '정렬 우선순위 (높을수록 먼저 표시)';

-- ==============================================================================
-- Sample Data (Optional - for testing)
-- ==============================================================================

-- Uncomment to insert sample data for testing
/*
INSERT INTO government_policies (
    policy_name, policy_code, policy_type, target_demographic,
    summary, description, benefits,
    age_min, age_max, income_max,
    is_active, priority
) VALUES
    (
        '청년전세임대주택',
        'YOUTH_JEONSE_2024',
        '임대지원',
        '청년',
        '청년층 주거 안정을 위한 전세임대 지원',
        '대학생 및 취업준비생을 대상으로 전세임대 주택을 지원하는 정책입니다. 시세의 30% 수준으로 임대료를 지원하며, 최대 2년간 거주 가능합니다.',
        '시세 30% 수준의 저렴한 임대료, 최대 2년 거주 지원, 계약갱신 가능',
        19, 39, 20000000,  -- 19-39세, 연소득 2천만원 이하
        true, 10
    ),
    (
        '신혼부부 특별공급',
        'NEWLYWED_SPECIAL_2024',
        '특별공급',
        '신혼부부',
        '신혼부부를 위한 주택 특별 공급',
        '혼인 기간 7년 이내의 신혼부부에게 아파트 등 공공주택을 우선 공급하는 제도입니다. 소득 및 자산 요건을 충족하는 경우 일반 공급보다 높은 당첨 확률을 제공합니다.',
        '일반 공급 대비 높은 당첨 확률, 시중 시세 대비 저렴한 가격, 장기 거주 가능',
        NULL, NULL, 70000000,  -- 연소득 7천만원 이하
        true, 9
    ),
    (
        '생애최초 특별공급',
        'FIRST_HOME_SPECIAL_2024',
        '특별공급',
        '생애최초',
        '생애 최초 주택 구입자를 위한 특별 공급',
        '생애 최초로 주택을 구입하는 무주택 세대주에게 공공주택을 특별 공급하는 제도입니다. 소득 요건을 충족하는 경우 일반 공급보다 유리한 조건으로 주택을 구입할 수 있습니다.',
        '특별 공급 기회, 저금리 대출 연계, 취득세 감면 혜택',
        NULL, NULL, 80000000,  -- 연소득 8천만원 이하
        true, 8
    ),
    (
        'HUG 전세보증보험',
        'HUG_JEONSE_INSURANCE_2024',
        '보증지원',
        '일반',
        '전세 계약 보증을 위한 보험 상품',
        '전세 계약 시 보증금 반환을 보증하는 보험 상품입니다. 임대인의 보증금 미반환 위험으로부터 임차인을 보호하며, 주택도시보증공사(HUG)에서 운영합니다.',
        '보증금 반환 보장, 전세 사기 예방, 안심 전세 계약',
        NULL, NULL, NULL,  -- 소득 제한 없음
        true, 7
    ),
    (
        '버팀목 전세자금대출',
        'STEPPING_STONE_JEONSE_2024',
        '대출지원',
        '저소득층',
        '저소득층 및 서민을 위한 전세자금 대출',
        '무주택자 또는 1주택 보유 세대주에게 저금리로 전세자금을 대출해주는 정책입니다. 주택금융공사(HF)에서 운영하며, 시중 금리보다 낮은 이자율을 적용합니다.',
        '저금리 대출, 최대 3억원 지원, 최장 10년 상환',
        NULL, NULL, 50000000,  -- 연소득 5천만원 이하
        true, 6
    );
*/
