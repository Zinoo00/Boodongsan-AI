"""
사용자 프로파일링 서비스
개체 추출 결과를 기반으로 사용자 프로필 생성 및 업데이트
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..database.connection import get_db_session
from ..database.models import ConversationHistory, User, UserPreference
from .policy_service import PolicyService

logger = logging.getLogger(__name__)

class UserProfilingService:
    """사용자 프로파일링 서비스"""
    
    def __init__(self):
        self.policy_service = PolicyService()
    
    async def create_or_update_profile(
        self, 
        user_id: str,
        extracted_entities: dict[str, Any],
        session_id: str = None
    ) -> dict[str, Any]:
        """사용자 프로필 생성 또는 업데이트"""
        try:
            async with get_db_session() as db:
                # 기존 사용자 조회
                user = await self._get_or_create_user(db, user_id, extracted_entities)
                
                # 사용자 기본 정보 업데이트
                user = await self._update_user_basic_info(db, user, extracted_entities)
                
                # 사용자 선호도 업데이트
                preference = await self._update_user_preferences(db, user, extracted_entities)
                
                # 프로필 완성도 계산
                completeness = self._calculate_profile_completeness(user, preference)
                
                # 적용 가능한 정책 확인
                applicable_policies = await self.policy_service.find_applicable_policies(
                    self._user_to_dict(user)
                )
                
                # 프로필 딕셔너리 생성
                profile = {
                    "user_id": str(user.id),
                    "basic_info": self._user_to_dict(user),
                    "preferences": self._preference_to_dict(preference) if preference else {},
                    "completeness": completeness,
                    "applicable_policies": [
                        {
                            "id": str(policy.id),
                            "name": policy.policy_name,
                            "type": policy.policy_type,
                            "description": policy.description
                        }
                        for policy in applicable_policies
                    ],
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                await db.commit()
                
                logger.info(f"사용자 프로필 업데이트 완료: {user_id}")
                return profile
                
        except Exception as e:
            logger.error(f"사용자 프로필 업데이트 실패: {str(e)}")
            raise
    
    async def _get_or_create_user(
        self, 
        db: Session, 
        user_id: str,
        extracted_entities: dict[str, Any]
    ) -> User:
        """사용자 조회 또는 생성"""
        try:
            # UUID 형태의 user_id인 경우 직접 조회
            if len(user_id) == 36:  # UUID 길이
                user = db.query(User).filter(User.id == user_id).first()
            else:
                user = None
            
            if not user:
                # 새 사용자 생성
                user = User(
                    name=extracted_entities.get("name", "사용자"),
                    age=extracted_entities.get("age", 30),
                    annual_income=extracted_entities.get("income", 0),
                    job_type=extracted_entities.get("job_type"),
                    marital_status=extracted_entities.get("marital_status"),
                    dependents=extracted_entities.get("dependents", 0),
                    region_preference=extracted_entities.get("region"),
                    budget_min=extracted_entities.get("budget_min"),
                    budget_max=extracted_entities.get("budget_max")
                )
                
                # 특별 조건 설정
                user.is_newlywed = extracted_entities.get("is_newlywed", False)
                user.has_multiple_children = extracted_entities.get("has_multiple_children", False)
                user.is_first_time_buyer = extracted_entities.get("is_first_time_buyer", True)
                
                db.add(user)
                await db.flush()  # ID 생성
                
                logger.info(f"새 사용자 생성: {user.id}")
            
            return user
            
        except Exception as e:
            logger.error(f"사용자 조회/생성 실패: {str(e)}")
            raise
    
    async def _update_user_basic_info(
        self, 
        db: Session, 
        user: User,
        extracted_entities: dict[str, Any]
    ) -> User:
        """사용자 기본 정보 업데이트"""
        try:
            # 추출된 엔티티로 사용자 정보 업데이트
            if extracted_entities.get("age"):
                user.age = extracted_entities["age"]
            
            if extracted_entities.get("income"):
                user.annual_income = extracted_entities["income"]
            
            if extracted_entities.get("job_type"):
                user.job_type = extracted_entities["job_type"]
            
            if extracted_entities.get("marital_status"):
                user.marital_status = extracted_entities["marital_status"]
            
            if "dependents" in extracted_entities and extracted_entities["dependents"] is not None:
                user.dependents = extracted_entities["dependents"]
            
            if extracted_entities.get("region"):
                user.region_preference = extracted_entities["region"]
            
            # 예산 정보 업데이트
            if extracted_entities.get("budget_min"):
                user.budget_min = extracted_entities["budget_min"]
            
            if extracted_entities.get("budget_max"):
                user.budget_max = extracted_entities["budget_max"]
            
            # 단일 예산이 주어진 경우 범위로 변환
            if extracted_entities.get("budget"):
                budget = extracted_entities["budget"]
                if not user.budget_min and not user.budget_max:
                    # 예산의 ±20% 범위로 설정
                    user.budget_min = int(budget * 0.8)
                    user.budget_max = int(budget * 1.2)
            
            # 특별 조건 업데이트
            if "is_newlywed" in extracted_entities:
                user.is_newlywed = extracted_entities["is_newlywed"]
            
            if "has_multiple_children" in extracted_entities:
                user.has_multiple_children = extracted_entities["has_multiple_children"]
            
            if "is_first_time_buyer" in extracted_entities:
                user.is_first_time_buyer = extracted_entities["is_first_time_buyer"]
            
            # 신혼부부 키워드 감지
            text_content = str(extracted_entities.get("original_text", "")).lower()
            if any(keyword in text_content for keyword in ["신혼부부", "신혼", "결혼"]):
                user.is_newlywed = True
            
            # 다자녀 키워드 감지
            if any(keyword in text_content for keyword in ["다자녀", "아이", "자녀"]):
                if user.dependents >= 2:
                    user.has_multiple_children = True
            
            user.updated_at = datetime.utcnow()
            
            return user
            
        except Exception as e:
            logger.error(f"사용자 기본 정보 업데이트 실패: {str(e)}")
            raise
    
    async def _update_user_preferences(
        self, 
        db: Session, 
        user: User,
        extracted_entities: dict[str, Any]
    ) -> UserPreference | None:
        """사용자 선호도 업데이트"""
        try:
            # 기존 선호도 조회
            preference = db.query(UserPreference).filter(
                UserPreference.user_id == user.id
            ).first()
            
            if not preference:
                preference = UserPreference(user_id=user.id)
                db.add(preference)
            
            # 부동산 유형 업데이트
            if extracted_entities.get("property_type"):
                preference.property_type = extracted_entities["property_type"]
            
            # 방 개수 업데이트
            if extracted_entities.get("room_count"):
                preference.room_count = extracted_entities["room_count"]
            
            # 면적 정보 업데이트
            if extracted_entities.get("area_min"):
                preference.area_min = extracted_entities["area_min"]
            
            if extracted_entities.get("area_max"):
                preference.area_max = extracted_entities["area_max"]
            
            # 단일 면적이 주어진 경우 범위로 변환
            if extracted_entities.get("area"):
                area = extracted_entities["area"]
                if not preference.area_min and not preference.area_max:
                    # 면적의 ±5평 범위로 설정
                    preference.area_min = max(1, area - 5)
                    preference.area_max = area + 5
            
            # 중요도 점수 추론 (키워드 기반)
            text_content = str(extracted_entities.get("original_text", "")).lower()
            
            # 교통 중요도
            if any(keyword in text_content for keyword in ["지하철", "버스", "교통", "출퇴근"]):
                preference.transportation_importance = 5
            elif any(keyword in text_content for keyword in ["차", "자동차", "주차"]):
                preference.parking_importance = 5
            
            # 학군 중요도
            if any(keyword in text_content for keyword in ["학교", "학군", "교육", "아이"]):
                preference.school_district_importance = 5
            
            # 편의시설 중요도
            if any(keyword in text_content for keyword in ["마트", "쇼핑", "병원", "편의시설"]):
                preference.amenities_importance = 5
            
            # 보안 중요도
            if any(keyword in text_content for keyword in ["안전", "보안", "cctv", "경비"]):
                preference.security_importance = 5
            
            preference.updated_at = datetime.utcnow()
            
            return preference
            
        except Exception as e:
            logger.error(f"사용자 선호도 업데이트 실패: {str(e)}")
            return None
    
    def _calculate_profile_completeness(
        self, 
        user: User, 
        preference: UserPreference | None
    ) -> float:
        """프로필 완성도 계산 (0.0 ~ 1.0)"""
        try:
            total_fields = 0
            completed_fields = 0
            
            # 필수 필드 체크
            essential_fields = [
                user.age, user.annual_income, user.region_preference,
                user.budget_min or user.budget_max
            ]
            
            for field in essential_fields:
                total_fields += 1
                if field:
                    completed_fields += 1
            
            # 선택적 필드 체크
            optional_fields = [
                user.job_type, user.marital_status,
                user.dependents, user.budget_min, user.budget_max
            ]
            
            for field in optional_fields:
                total_fields += 1
                if field:
                    completed_fields += 1
            
            # 선호도 필드 체크
            if preference:
                preference_fields = [
                    preference.property_type, preference.room_count,
                    preference.area_min, preference.area_max
                ]
                
                for field in preference_fields:
                    total_fields += 1
                    if field:
                        completed_fields += 1
            
            completeness = completed_fields / total_fields if total_fields > 0 else 0.0
            return round(completeness, 2)
            
        except Exception as e:
            logger.error(f"프로필 완성도 계산 실패: {str(e)}")
            return 0.0
    
    def _user_to_dict(self, user: User) -> dict[str, Any]:
        """User 모델을 딕셔너리로 변환"""
        return {
            "id": str(user.id),
            "name": user.name,
            "age": user.age,
            "annual_income": user.annual_income,
            "job_type": user.job_type,
            "marital_status": user.marital_status,
            "dependents": user.dependents,
            "region_preference": user.region_preference,
            "budget_min": user.budget_min,
            "budget_max": user.budget_max,
            "is_first_time_buyer": user.is_first_time_buyer,
            "is_newlywed": user.is_newlywed,
            "has_multiple_children": user.has_multiple_children,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    
    def _preference_to_dict(self, preference: UserPreference) -> dict[str, Any]:
        """UserPreference 모델을 딕셔너리로 변환"""
        return {
            "property_type": preference.property_type,
            "room_count": preference.room_count,
            "area_min": preference.area_min,
            "area_max": preference.area_max,
            "transportation_importance": preference.transportation_importance,
            "school_district_importance": preference.school_district_importance,
            "amenities_importance": preference.amenities_importance,
            "security_importance": preference.security_importance,
            "parking_importance": preference.parking_importance
        }
    
    async def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """사용자 프로필 조회"""
        try:
            async with get_db_session() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return None
                
                preference = db.query(UserPreference).filter(
                    UserPreference.user_id == user.id
                ).first()
                
                completeness = self._calculate_profile_completeness(user, preference)
                
                # 적용 가능한 정책 확인
                applicable_policies = await self.policy_service.find_applicable_policies(
                    self._user_to_dict(user)
                )
                
                profile = {
                    "user_id": str(user.id),
                    "basic_info": self._user_to_dict(user),
                    "preferences": self._preference_to_dict(preference) if preference else {},
                    "completeness": completeness,
                    "applicable_policies": [
                        {
                            "id": str(policy.id),
                            "name": policy.policy_name,
                            "type": policy.policy_type,
                            "description": policy.description
                        }
                        for policy in applicable_policies
                    ]
                }
                
                return profile
                
        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패: {str(e)}")
            return None
    
    async def analyze_conversation_patterns(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> dict[str, Any]:
        """사용자 대화 패턴 분석"""
        try:
            async with get_db_session() as db:
                conversations = db.query(ConversationHistory).filter(
                    ConversationHistory.user_id == user_id
                ).order_by(
                    ConversationHistory.created_at.desc()
                ).limit(limit).all()
                
                if not conversations:
                    return {"message": "대화 이력이 없습니다."}
                
                # 의도 분포 분석
                intent_counts = {}
                for conv in conversations:
                    intent = conv.detected_intent or "UNKNOWN"
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1
                
                # 주요 관심사 추출
                all_entities = {}
                for conv in conversations:
                    if conv.extracted_entities:
                        entities = conv.extracted_entities
                        for key, value in entities.items():
                            if value:  # None이나 빈 값이 아닌 경우
                                if key not in all_entities:
                                    all_entities[key] = []
                                all_entities[key].append(value)
                
                # 일관성 있는 선호도 추출
                consistent_preferences = {}
                for key, values in all_entities.items():
                    if len(values) >= 2:  # 2번 이상 언급된 것들
                        # 가장 빈번한 값 찾기
                        from collections import Counter
                        most_common = Counter(values).most_common(1)
                        if most_common:
                            consistent_preferences[key] = most_common[0][0]
                
                analysis = {
                    "total_conversations": len(conversations),
                    "intent_distribution": intent_counts,
                    "main_interests": list(intent_counts.keys()),
                    "consistent_preferences": consistent_preferences,
                    "last_conversation": conversations[0].created_at.isoformat() if conversations else None
                }
                
                return analysis
                
        except Exception as e:
            logger.error(f"대화 패턴 분석 실패: {str(e)}")
            return {"error": "분석 중 오류가 발생했습니다."}
    
    async def suggest_missing_info(self, user_id: str) -> list[str]:
        """부족한 정보 제안"""
        try:
            profile = await self.get_user_profile(user_id)
            if not profile:
                return ["사용자 정보를 찾을 수 없습니다."]
            
            suggestions = []
            basic_info = profile.get("basic_info", {})
            preferences = profile.get("preferences", {})
            
            # 기본 정보 체크
            if not basic_info.get("age"):
                suggestions.append("나이 정보가 필요합니다. 몇 살이신가요?")
            
            if not basic_info.get("annual_income"):
                suggestions.append("연봉 정보가 있으면 더 정확한 정책을 추천드릴 수 있습니다.")
            
            if not basic_info.get("region_preference"):
                suggestions.append("희망 지역을 알려주시면 해당 지역 매물을 찾아드릴게요.")
            
            if not basic_info.get("budget_min") and not basic_info.get("budget_max"):
                suggestions.append("예산 범위를 알려주시면 조건에 맞는 매물을 추천드릴 수 있습니다.")
            
            # 선호도 정보 체크
            if not preferences.get("property_type"):
                suggestions.append("선호하시는 부동산 유형(아파트, 빌라 등)을 알려주세요.")
            
            if not preferences.get("room_count"):
                suggestions.append("희망하시는 방 개수를 알려주시면 도움이 됩니다.")
            
            # 특수 상황 체크
            if not basic_info.get("marital_status"):
                suggestions.append("결혼 여부에 따라 추가 혜택이 있을 수 있습니다.")
            
            return suggestions[:3]  # 최대 3개까지만 제안
            
        except Exception as e:
            logger.error(f"부족한 정보 제안 실패: {str(e)}")
            return ["정보 분석 중 오류가 발생했습니다."]