"""
정부 지원 정책 시드 데이터
실제 한국 정부 부동산 지원 정책들을 데이터베이스에 추가
"""

import asyncio
import logging
from datetime import datetime

from .connection import get_db_session
from .models import GovernmentPolicy, PolicyCondition

logger = logging.getLogger(__name__)

# 실제 한국 정부 부동산 지원 정책 데이터
GOVERNMENT_POLICIES_DATA = [
    {
        "policy_name": "청년전세임대주택",
        "policy_type": "임대주택",
        "policy_category": "청년",
        "description": "청년층을 위한 전세임대주택 지원 프로그램으로, 기존 주택을 임차하여 저렴하게 재임대하는 제도입니다.",
        "age_min": 19,
        "age_max": 39,
        "income_min": None,
        "income_max": 120000000,  # 1억 2천만원 이하
        "asset_limit": 29200000,  # 2천 920만원 이하
        "loan_limit": 120000000,
        "interest_rate": 1.2,
        "loan_period_max": 2,
        "available_regions": ["서울", "경기", "인천", "대전", "대구", "부산", "광주", "울산"],
        "first_time_buyer_only": False,
        "newlywed_priority": False,
        "multi_child_benefit": False,
        "application_url": "https://apply.lh.or.kr",
        "required_documents": [
            "신청서", "주민등록등본", "가족관계증명서", "소득증명서류", 
            "자산증명서류", "청년확인서"
        ],
        "contact_info": "LH 콜센터: 1600-1004"
    },
    {
        "policy_name": "LH청약플러스",
        "policy_type": "청약",
        "policy_category": "일반",
        "description": "LH 분양주택 및 임대주택 청약 시 추가 가점을 받을 수 있는 제도입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 130000000,  # 1억 3천만원 이하
        "asset_limit": None,
        "loan_limit": None,
        "interest_rate": None,
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": True,
        "multi_child_benefit": True,
        "application_url": "https://apply.lh.or.kr",
        "required_documents": ["신청서", "주민등록등본", "소득증명서류"],
        "contact_info": "LH 콜센터: 1600-1004"
    },
    {
        "policy_name": "HUG 전세보증보험",
        "policy_type": "보증보험",
        "policy_category": "일반",
        "description": "전세보증금 반환을 보장하는 보증보험으로, 임대인의 보증금 미반환 시 보상을 받을 수 있습니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": None,
        "asset_limit": None,
        "loan_limit": 300000000,  # 3억원까지 보장
        "interest_rate": None,
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": False,
        "multi_child_benefit": False,
        "application_url": "https://www.khug.or.kr",
        "required_documents": ["신청서", "전세계약서", "등기부등본", "주민등록등본"],
        "contact_info": "HUG 콜센터: 1688-8114"
    },
    {
        "policy_name": "디딤돌 대출",
        "policy_type": "구입자금",
        "policy_category": "일반",
        "description": "무주택 서민의 내집마련을 지원하는 정부지원 주택구입자금 대출입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 60000000,  # 6천만원 이하 (부부합산 7천만원)
        "asset_limit": 335000000,  # 3억 3천 5백만원 이하
        "loan_limit": 250000000,  # 2억 5천만원
        "interest_rate": 3.2,
        "loan_period_max": 40,
        "available_regions": ["전국"],
        "first_time_buyer_only": True,
        "newlywed_priority": False,
        "multi_child_benefit": False,
        "application_url": "https://www.khf.co.kr",
        "required_documents": [
            "대출신청서", "소득증명서류", "재산세 납세증명서", 
            "건축물대장등본", "매매계약서"
        ],
        "contact_info": "주택금융공사: 1688-8114"
    },
    {
        "policy_name": "생애최초 특별공급",
        "policy_type": "특별공급",
        "policy_category": "생애최초",
        "description": "생애최초로 주택을 구입하는 무주택자를 위한 특별공급 제도입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 130000000,  # 도시근로자 월평균소득 130% 이하
        "asset_limit": 335000000,
        "loan_limit": None,
        "interest_rate": None,
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": True,
        "newlywed_priority": False,
        "multi_child_benefit": False,
        "application_url": "https://apply.lh.or.kr",
        "required_documents": [
            "신청서", "무주택확인서", "소득증명서류", "자산증명서류",
            "생애최초 확인서"
        ],
        "contact_info": "LH 콜센터: 1600-1004"
    },
    {
        "policy_name": "신혼부부 특별공급",
        "policy_type": "특별공급",
        "policy_category": "신혼부부",
        "description": "혼인 기간 7년 이내의 신혼부부를 위한 주택 특별공급 제도입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 130000000,
        "asset_limit": 335000000,
        "loan_limit": None,
        "interest_rate": None,
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": True,
        "multi_child_benefit": False,
        "application_url": "https://apply.lh.or.kr",
        "required_documents": [
            "신청서", "주민등록등본", "가족관계증명서", 
            "혼인관계증명서", "소득증명서류"
        ],
        "contact_info": "LH 콜센터: 1600-1004"
    },
    {
        "policy_name": "다자녀 가구 특별공급",
        "policy_type": "특별공급",
        "policy_category": "다자녀",
        "description": "미성년 자녀 3명 이상을 둔 다자녀 가구를 위한 주택 특별공급 제도입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 160000000,  # 도시근로자 월평균소득 160% 이하
        "asset_limit": 335000000,
        "loan_limit": None,
        "interest_rate": None,
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": False,
        "multi_child_benefit": True,
        "application_url": "https://apply.lh.or.kr",
        "required_documents": [
            "신청서", "주민등록등본", "가족관계증명서",
            "자녀 출생증명서", "소득증명서류"
        ],
        "contact_info": "LH 콜센터: 1600-1004"
    },
    {
        "policy_name": "버팀목 전세자금대출",
        "policy_type": "전세자금",
        "policy_category": "일반",
        "description": "무주택 서민의 주거안정을 위한 전세자금 대출 상품입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 50000000,  # 5천만원 이하 (부부합산 6천만원)
        "asset_limit": 292000000,  # 2억 9천 2백만원 이하
        "loan_limit": 120000000,  # 1억 2천만원
        "interest_rate": 2.1,
        "loan_period_max": 2,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": True,
        "multi_child_benefit": True,
        "application_url": "https://www.khf.co.kr",
        "required_documents": [
            "대출신청서", "전세계약서", "소득증명서류",
            "재산세 납세증명서", "주민등록등본"
        ],
        "contact_info": "주택금융공사: 1688-8114"
    },
    {
        "policy_name": "청년 우대형 청약통장",
        "policy_type": "청약",
        "policy_category": "청년",
        "description": "만 19세~34세 청년을 위한 우대금리 청약저축 상품입니다.",
        "age_min": 19,
        "age_max": 34,
        "income_min": None,
        "income_max": 36000000,  # 3천 6백만원 이하
        "asset_limit": None,
        "loan_limit": None,
        "interest_rate": 3.3,  # 우대금리
        "loan_period_max": None,
        "available_regions": ["전국"],
        "first_time_buyer_only": False,
        "newlywed_priority": False,
        "multi_child_benefit": False,
        "application_url": "https://www.khf.co.kr",
        "required_documents": ["신청서", "신분증", "소득증명서류"],
        "contact_info": "주택금융공사: 1688-8114"
    },
    {
        "policy_name": "내집마련 디딤돌 대출",
        "policy_type": "구입자금",
        "policy_category": "일반",
        "description": "생애최초 주택구입자를 위한 장기 저금리 대출 상품입니다.",
        "age_min": None,
        "age_max": None,
        "income_min": None,
        "income_max": 70000000,  # 7천만원 이하 (부부합산 8천만원)
        "asset_limit": 335000000,
        "loan_limit": 300000000,  # 3억원
        "interest_rate": 3.05,
        "loan_period_max": 40,
        "available_regions": ["전국"],
        "first_time_buyer_only": True,
        "newlywed_priority": True,
        "multi_child_benefit": True,
        "application_url": "https://www.khf.co.kr",
        "required_documents": [
            "대출신청서", "무주택확인서", "소득증명서류",
            "매매계약서", "건축물대장등본"
        ],
        "contact_info": "주택금융공사: 1688-8114"
    }
]

async def seed_government_policies():
    """정부 지원 정책 시드 데이터 추가"""
    try:
        async with get_db_session() as db:
            # 기존 데이터 확인
            existing_count = db.query(GovernmentPolicy).count()
            if existing_count > 0:
                logger.info(f"기존 정책 데이터 {existing_count}개가 존재합니다. 스킵합니다.")
                return
            
            logger.info("정부 지원 정책 시드 데이터 추가 시작...")
            
            policies_created = 0
            
            for policy_data in GOVERNMENT_POLICIES_DATA:
                # 정책 생성
                policy = GovernmentPolicy(
                    policy_name=policy_data["policy_name"],
                    policy_type=policy_data["policy_type"],
                    policy_category=policy_data["policy_category"],
                    description=policy_data["description"],
                    age_min=policy_data["age_min"],
                    age_max=policy_data["age_max"],
                    income_min=policy_data["income_min"],
                    income_max=policy_data["income_max"],
                    asset_limit=policy_data["asset_limit"],
                    loan_limit=policy_data["loan_limit"],
                    interest_rate=policy_data["interest_rate"],
                    loan_period_max=policy_data["loan_period_max"],
                    available_regions=policy_data["available_regions"],
                    first_time_buyer_only=policy_data["first_time_buyer_only"],
                    newlywed_priority=policy_data["newlywed_priority"],
                    multi_child_benefit=policy_data["multi_child_benefit"],
                    application_url=policy_data["application_url"],
                    required_documents=policy_data["required_documents"],
                    contact_info=policy_data["contact_info"],
                    is_active=True,
                    start_date=datetime.now().date(),
                    end_date=None  # 종료일 미정
                )
                
                db.add(policy)
                await db.flush()  # ID 생성을 위해
                
                # 추가 세부 조건이 있다면 PolicyCondition에 추가
                # (여기서는 기본 조건들만 GovernmentPolicy 테이블에 저장)
                
                policies_created += 1
                logger.info(f"정책 추가됨: {policy.policy_name}")
            
            await db.commit()
            logger.info(f"총 {policies_created}개 정부 지원 정책 추가 완료")
            
    except Exception as e:
        logger.error(f"정부 지원 정책 시드 데이터 추가 실패: {str(e)}")
        raise

async def add_policy_conditions():
    """정책별 세부 조건 추가"""
    try:
        async with get_db_session() as db:
            # 청년전세임대주택 세부 조건
            youth_policy = db.query(GovernmentPolicy).filter(
                GovernmentPolicy.policy_name == "청년전세임대주택"
            ).first()
            
            if youth_policy:
                conditions = [
                    {
                        "condition_type": "거주지역",
                        "condition_key": "current_address",
                        "condition_value": "해당지역 거주 또는 근무",
                        "condition_operator": "IN",
                        "description": "해당 지역에 거주하거나 근무하는 자",
                        "is_required": True
                    },
                    {
                        "condition_type": "보증금",
                        "condition_key": "deposit_ratio",
                        "condition_value": "0.05",
                        "condition_operator": ">=",
                        "description": "임차보증금의 5% 이상 자기부담",
                        "is_required": True
                    }
                ]
                
                for cond_data in conditions:
                    condition = PolicyCondition(
                        policy_id=youth_policy.id,
                        **cond_data
                    )
                    db.add(condition)
            
            # 디딤돌 대출 세부 조건
            didimstone_policy = db.query(GovernmentPolicy).filter(
                GovernmentPolicy.policy_name == "디딤돌 대출"
            ).first()
            
            if didimstone_policy:
                conditions = [
                    {
                        "condition_type": "주택가격",
                        "condition_key": "house_price",
                        "condition_value": "600000000",
                        "condition_operator": "<=",
                        "description": "주택가격 6억원 이하",
                        "is_required": True
                    },
                    {
                        "condition_type": "대출비율",
                        "condition_key": "ltv_ratio",
                        "condition_value": "0.70",
                        "condition_operator": "<=",
                        "description": "LTV 70% 이하",
                        "is_required": True
                    }
                ]
                
                for cond_data in conditions:
                    condition = PolicyCondition(
                        policy_id=didimstone_policy.id,
                        **cond_data
                    )
                    db.add(condition)
            
            await db.commit()
            logger.info("정책 세부 조건 추가 완료")
            
    except Exception as e:
        logger.error(f"정책 세부 조건 추가 실패: {str(e)}")
        raise

async def update_policy_data():
    """정책 데이터 업데이트 (정기적으로 실행)"""
    try:
        async with get_db_session() as db:
            # 금리 업데이트 (예시)
            policies_to_update = [
                ("버팀목 전세자금대출", 2.3),
                ("디딤돌 대출", 3.4),
                ("내집마련 디딤돌 대출", 3.15)
            ]
            
            for policy_name, new_rate in policies_to_update:
                policy = db.query(GovernmentPolicy).filter(
                    GovernmentPolicy.policy_name == policy_name
                ).first()
                
                if policy:
                    old_rate = policy.interest_rate
                    policy.interest_rate = new_rate
                    policy.updated_at = datetime.utcnow()
                    
                    logger.info(f"{policy_name} 금리 업데이트: {old_rate}% → {new_rate}%")
            
            await db.commit()
            logger.info("정책 데이터 업데이트 완료")
            
    except Exception as e:
        logger.error(f"정책 데이터 업데이트 실패: {str(e)}")
        raise

async def get_policy_statistics():
    """정책 통계 조회"""
    try:
        async with get_db_session() as db:
            total_policies = db.query(GovernmentPolicy).count()
            active_policies = db.query(GovernmentPolicy).filter(
                GovernmentPolicy.is_active == True
            ).count()
            
            # 정책 유형별 통계
            policy_types = db.query(
                GovernmentPolicy.policy_type,
                db.func.count(GovernmentPolicy.id)
            ).group_by(
                GovernmentPolicy.policy_type
            ).all()
            
            # 정책 카테고리별 통계
            policy_categories = db.query(
                GovernmentPolicy.policy_category,
                db.func.count(GovernmentPolicy.id)
            ).group_by(
                GovernmentPolicy.policy_category
            ).all()
            
            statistics = {
                "total_policies": total_policies,
                "active_policies": active_policies,
                "policy_types": dict(policy_types),
                "policy_categories": dict(policy_categories),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            return statistics
            
    except Exception as e:
        logger.error(f"정책 통계 조회 실패: {str(e)}")
        return {}

if __name__ == "__main__":
    # 스크립트 직접 실행 시
    async def main():
        await seed_government_policies()
        await add_policy_conditions()
        stats = await get_policy_statistics()
        print("정책 통계:", stats)
    
    asyncio.run(main())