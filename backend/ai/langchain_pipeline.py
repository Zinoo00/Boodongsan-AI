"""
LangChain 기반 AI 파이프라인 구현
부동산 추천을 위한 체인 및 에이전트 관리
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from langchain.chains import ConversationChain, LLMChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain.tools import BaseTool

from ..services.policy_service import PolicyService
from ..services.property_service import PropertyService
from .bedrock_client import get_bedrock_client

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """대화 컨텍스트 관리"""

    user_id: str
    session_id: str
    user_profile: dict[str, Any] | None = None
    conversation_history: list[dict[str, str]] = None
    extracted_entities: dict[str, Any] = None
    current_intent: str = "GENERAL_CHAT"


class PropertySearchTool(BaseTool):
    """부동산 검색 도구"""

    name = "property_search"
    description = "부동산 매물을 검색합니다. 지역, 가격대, 매물 유형 등의 조건을 받습니다."

    def __init__(self, property_service: PropertyService):
        super().__init__()
        self.property_service = property_service

    def _run(self, query: str) -> str:
        """부동산 검색 실행"""
        try:
            # 쿼리 파싱 (실제로는 더 정교한 파싱 필요)
            # 여기서는 간단한 예시만 구현
            results = asyncio.run(self.property_service.search_properties(query))

            if not results:
                return "검색 조건에 맞는 부동산을 찾을 수 없습니다."

            # 결과 포맷팅
            formatted_results = []
            for prop in results[:3]:  # 상위 3개만
                formatted_results.append(
                    f"- {prop.title}: {prop.district} {prop.dong}, "
                    f"{prop.price:,}원, {prop.area_exclusive}㎡"
                )

            return "\n".join(formatted_results)

        except Exception as e:
            logger.error(f"부동산 검색 실패: {str(e)}")
            return "부동산 검색 중 오류가 발생했습니다."

    async def _arun(self, query: str) -> str:
        """비동기 부동산 검색 실행"""
        return self._run(query)


class PolicySearchTool(BaseTool):
    """정부 정책 검색 도구"""

    name = "policy_search"
    description = "정부 지원 정책을 검색합니다. 사용자의 나이, 소득 등 조건을 기반으로 적용 가능한 정책을 찾습니다."

    def __init__(self, policy_service: PolicyService):
        super().__init__()
        self.policy_service = policy_service

    def _run(self, user_profile: str) -> str:
        """정책 검색 실행"""
        try:
            # user_profile은 JSON 문자열로 전달됨
            import json

            profile_dict = json.loads(user_profile)

            results = asyncio.run(self.policy_service.find_applicable_policies(profile_dict))

            if not results:
                return "적용 가능한 정부 지원 정책을 찾을 수 없습니다."

            # 결과 포맷팅
            formatted_results = []
            for policy in results:
                formatted_results.append(
                    f"- {policy.policy_name}: {policy.description}\n"
                    f"  대출한도: {policy.loan_limit:,}원, "
                    f"금리: {policy.interest_rate}%"
                )

            return "\n".join(formatted_results)

        except Exception as e:
            logger.error(f"정책 검색 실패: {str(e)}")
            return "정책 검색 중 오류가 발생했습니다."

    async def _arun(self, user_profile: str) -> str:
        """비동기 정책 검색 실행"""
        return self._run(user_profile)


class RealEstateAgent:
    """부동산 상담 AI 에이전트"""

    def __init__(self):
        self.bedrock_client = get_bedrock_client()
        self.property_service = PropertyService()
        self.policy_service = PolicyService()
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            k=10,  # 최근 10개 대화만 유지
            return_messages=True,
        )
        self._initialize_tools()
        self._initialize_chains()

    def _initialize_tools(self):
        """도구 초기화"""
        self.tools = [
            PropertySearchTool(self.property_service),
            PolicySearchTool(self.policy_service),
        ]

    def _initialize_chains(self):
        """체인 초기화"""
        # 대화 체인
        conversation_prompt = PromptTemplate(
            input_variables=["chat_history", "input"],
            template="""
            당신은 한국 부동산 전문 상담사입니다.
            사용자의 개인 상황을 파악하고 맞춤형 부동산과 정부 지원 정책을 추천해주세요.
            
            대화 기록:
            {chat_history}
            
            사용자: {input}
            상담사:
            """,
        )

        self.conversation_chain = ConversationChain(
            llm=self.bedrock_client.llm,
            prompt=conversation_prompt,
            memory=self.memory,
            verbose=True,
        )

        # 개체 추출 체인
        entity_extraction_prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            다음 텍스트에서 부동산 상담에 필요한 정보를 추출해주세요:
            
            텍스트: {text}
            
            추출할 정보:
            - age: 나이
            - income: 연봉 (원 단위)
            - region: 희망 지역
            - property_type: 부동산 유형
            - transaction_type: 거래 유형 (매매/전세/월세)
            - budget: 예산
            - room_count: 희망 방 개수
            - special_conditions: 특별 조건 (신혼부부, 다자녀 등)
            
            JSON 형태로 반환해주세요:
            """,
        )

        self.entity_extraction_chain = LLMChain(
            llm=self.bedrock_client.llm, prompt=entity_extraction_prompt
        )

    async def process_message(
        self, message: str, context: ConversationContext
    ) -> tuple[str, ConversationContext]:
        """메시지 처리 메인 함수"""
        try:
            # 1. 의도 분류
            intent = await self.bedrock_client.classify_intent(message)
            context.current_intent = intent

            # 2. 개체 추출
            entities = await self.bedrock_client.extract_entities(message)
            if entities:
                # 기존 개체 정보와 병합
                if context.extracted_entities:
                    context.extracted_entities.update(entities)
                else:
                    context.extracted_entities = entities

            # 3. 의도별 처리
            if intent == "PROPERTY_SEARCH":
                response = await self._handle_property_search(message, context)
            elif intent == "POLICY_INQUIRY":
                response = await self._handle_policy_inquiry(message, context)
            elif intent == "MARKET_INFO":
                response = await self._handle_market_info(message, context)
            else:
                response = await self._handle_general_chat(message, context)

            # 4. 대화 기록 업데이트
            if context.conversation_history is None:
                context.conversation_history = []

            context.conversation_history.append({"role": "user", "content": message})
            context.conversation_history.append({"role": "assistant", "content": response})

            return response, context

        except Exception as e:
            logger.error(f"메시지 처리 실패: {str(e)}")
            return "죄송합니다. 처리 중 오류가 발생했습니다.", context

    async def _handle_property_search(self, message: str, context: ConversationContext) -> str:
        """부동산 검색 처리"""
        try:
            # 검색 조건 구성
            search_criteria = {}
            if context.extracted_entities:
                search_criteria.update(context.extracted_entities)

            # 부동산 검색
            properties = await self.property_service.search_properties_by_criteria(search_criteria)

            if not properties:
                return """
                검색 조건에 맞는 부동산을 찾을 수 없습니다.
                조건을 조정해서 다시 검색해보시거나, 더 자세한 정보를 알려주세요.
                
                예를 들어:
                - 지역을 넓혀보세요
                - 예산 범위를 조정해보세요
                - 다른 부동산 유형도 고려해보세요
                """

            # 정부 정책 매칭
            applicable_policies = []
            if context.extracted_entities:
                applicable_policies = await self.policy_service.find_applicable_policies(
                    context.extracted_entities
                )

            # 응답 생성
            response = await self.bedrock_client.generate_recommendation_text(
                user_profile=context.extracted_entities or {},
                matched_policies=applicable_policies,
                recommended_properties=properties[:3],
            )

            return response

        except Exception as e:
            logger.error(f"부동산 검색 처리 실패: {str(e)}")
            return "부동산 검색 중 오류가 발생했습니다."

    async def _handle_policy_inquiry(self, message: str, context: ConversationContext) -> str:
        """정책 문의 처리"""
        try:
            if not context.extracted_entities:
                return """
                정부 지원 정책을 안내해드리기 위해 몇 가지 정보가 필요합니다:
                
                1. 나이: 몇 살이신가요?
                2. 연봉: 연간 소득이 어떻게 되시나요?
                3. 가족 상황: 신혼부부, 다자녀 가구 등 특별한 상황이 있으신가요?
                4. 희망 지역: 어느 지역을 원하시나요?
                
                이 정보를 알려주시면 적용 가능한 정책을 찾아드릴게요!
                """

            # 적용 가능한 정책 검색
            policies = await self.policy_service.find_applicable_policies(
                context.extracted_entities
            )

            if not policies:
                return """
                현재 조건으로는 적용 가능한 정부 지원 정책을 찾을 수 없습니다.
                
                하지만 다음과 같은 일반적인 정책들을 확인해보세요:
                - 청년 우대형 청약통장
                - 주택청약종합저축
                - 디딤돌 대출
                
                더 자세한 상담을 원하시면 한국주택금융공사나 LH에 직접 문의해보시기 바랍니다.
                """

            # 정책 정보 포맷팅
            policy_info = []
            for policy in policies:
                info = f"""
                📋 **{policy.policy_name}**
                - 설명: {policy.description}
                - 대출한도: {policy.loan_limit:,}원
                - 금리: {policy.interest_rate}%
                - 대출기간: 최대 {policy.loan_period_max}년
                """

                if policy.age_min or policy.age_max:
                    age_range = (
                        f"{policy.age_min or '제한없음'}세 ~ {policy.age_max or '제한없음'}세"
                    )
                    info += f"\n- 나이 조건: {age_range}"

                if policy.income_max:
                    info += f"\n- 소득 조건: 연소득 {policy.income_max:,}원 이하"

                policy_info.append(info)

            response = "적용 가능한 정부 지원 정책을 찾았습니다:\n\n"
            response += "\n".join(policy_info)
            response += "\n\n💡 각 정책의 자세한 신청 방법은 해당 기관에 문의하시기 바랍니다."

            return response

        except Exception as e:
            logger.error(f"정책 문의 처리 실패: {str(e)}")
            return "정책 정보 조회 중 오류가 발생했습니다."

    async def _handle_market_info(self, message: str, context: ConversationContext) -> str:
        """시장 정보 문의 처리"""
        # 실제로는 외부 API나 데이터베이스에서 시장 정보를 가져와야 함
        system_prompt = """
        당신은 한국 부동산 시장 전문가입니다.
        사용자의 시장 정보 문의에 대해 전문적이고 객관적인 답변을 제공해주세요.
        최신 시장 동향, 정책 변화, 투자 조언 등을 포함해주세요.
        """

        messages = [{"role": "user", "content": message}]
        response = await self.bedrock_client.generate_response(messages, system_prompt)

        return response

    async def _handle_general_chat(self, message: str, context: ConversationContext) -> str:
        """일반 대화 처리"""
        system_prompt = """
        당신은 친근한 부동산 상담사입니다.
        사용자와 자연스럽게 대화하면서 부동산 관련 도움을 제공해주세요.
        필요시 추가 정보를 요청하거나 구체적인 상담을 안내해주세요.
        """

        messages = context.conversation_history or []
        messages.append({"role": "user", "content": message})

        response = await self.bedrock_client.generate_response(messages, system_prompt)

        return response


# 전역 에이전트 인스턴스
_agent = None


def get_real_estate_agent() -> RealEstateAgent:
    """부동산 에이전트 싱글톤 반환"""
    global _agent
    if _agent is None:
        _agent = RealEstateAgent()
    return _agent


async def initialize_agent():
    """에이전트 초기화"""
    global _agent
    _agent = RealEstateAgent()
    logger.info("부동산 AI 에이전트 초기화 완료")
