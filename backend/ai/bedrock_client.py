"""
AWS Bedrock 클라이언트 구현
Claude-3 모델을 사용한 자연어 처리 및 대화 관리
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError
import asyncio
import aiohttp
from langchain.llms.bedrock import Bedrock
from langchain.embeddings import BedrockEmbeddings
from langchain.schema import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

@dataclass
class BedrockConfig:
    """Bedrock 설정 클래스"""
    region_name: str = "us-east-1"
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    embedding_model_id: str = "amazon.titan-embed-text-v1"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9

class BedrockClient:
    """AWS Bedrock 클라이언트"""
    
    def __init__(self, config: BedrockConfig = None):
        self.config = config or BedrockConfig()
        self.bedrock_client = None
        self.bedrock_runtime = None
        self.llm = None
        self.embeddings = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Bedrock 클라이언트 초기화"""
        try:
            # Bedrock 클라이언트 생성
            self.bedrock_client = boto3.client(
                service_name='bedrock',
                region_name=self.config.region_name
            )
            
            # Bedrock Runtime 클라이언트 생성
            self.bedrock_runtime = boto3.client(
                service_name='bedrock-runtime',
                region_name=self.config.region_name
            )
            
            # LangChain Bedrock LLM 초기화
            self.llm = Bedrock(
                client=self.bedrock_runtime,
                model_id=self.config.model_id,
                model_kwargs={
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                }
            )
            
            # Bedrock Embeddings 초기화
            self.embeddings = BedrockEmbeddings(
                client=self.bedrock_runtime,
                model_id=self.config.embedding_model_id
            )
            
            logger.info("Bedrock 클라이언트 초기화 완료")
            
        except Exception as e:
            logger.error(f"Bedrock 클라이언트 초기화 실패: {str(e)}")
            raise
    
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = None
    ) -> str:
        """대화 기반 응답 생성"""
        try:
            # 메시지 포맷팅
            formatted_messages = []
            
            if system_prompt:
                formatted_messages.append(SystemMessage(content=system_prompt))
            
            for message in messages:
                if message["role"] == "user":
                    formatted_messages.append(HumanMessage(content=message["content"]))
                elif message["role"] == "assistant":
                    formatted_messages.append(AIMessage(content=message["content"]))
            
            # Claude-3 모델 호출
            response = await asyncio.to_thread(
                self._invoke_claude, formatted_messages
            )
            
            return response
            
        except Exception as e:
            logger.error(f"응답 생성 실패: {str(e)}")
            raise
    
    def _invoke_claude(self, messages: List) -> str:
        """Claude-3 모델 직접 호출"""
        try:
            # Anthropic Claude-3 API 포맷으로 변환
            anthropic_messages = []
            system_content = ""
            
            for message in messages:
                if isinstance(message, SystemMessage):
                    system_content = message.content
                elif isinstance(message, HumanMessage):
                    anthropic_messages.append({
                        "role": "user",
                        "content": message.content
                    })
                elif isinstance(message, AIMessage):
                    anthropic_messages.append({
                        "role": "assistant", 
                        "content": message.content
                    })
            
            # 요청 바디 구성
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "messages": anthropic_messages
            }
            
            if system_content:
                body["system"] = system_content
            
            # Bedrock Runtime 호출
            response = self.bedrock_runtime.invoke_model(
                modelId=self.config.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            # 응답 파싱
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
            
        except ClientError as e:
            logger.error(f"Bedrock 모델 호출 실패: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Claude 호출 중 오류: {str(e)}")
            raise
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트 임베딩 생성"""
        try:
            embeddings = await asyncio.to_thread(
                self.embeddings.embed_documents, texts
            )
            return embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            raise
    
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """사용자 메시지에서 개체 추출"""
        try:
            system_prompt = """
            당신은 부동산 상담 챗봇의 개체 추출 전문가입니다.
            사용자의 메시지에서 다음 정보를 추출해주세요:
            
            - age: 나이 (정수)
            - income: 연봉 (정수, 원 단위)
            - region: 희망 지역 (문자열)
            - property_type: 부동산 유형 (아파트, 빌라, 오피스텔, 단독주택 등)
            - transaction_type: 거래 유형 (매매, 전세, 월세)
            - budget_min: 최소 예산 (정수, 원 단위)
            - budget_max: 최대 예산 (정수, 원 단위)
            - room_count: 방 개수 (정수)
            - area: 면적 (정수, 평 단위)
            
            추출된 정보를 JSON 형태로 반환해주세요.
            정보가 없는 경우 null로 표시해주세요.
            """
            
            messages = [{"role": "user", "content": text}]
            response = await self.generate_response(messages, system_prompt)
            
            # JSON 파싱 시도
            try:
                entities = json.loads(response)
                return entities
            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패, 원본 응답: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"개체 추출 실패: {str(e)}")
            return {}
    
    async def classify_intent(self, text: str) -> str:
        """사용자 의도 분류"""
        try:
            system_prompt = """
            당신은 부동산 상담 챗봇의 의도 분류 전문가입니다.
            사용자의 메시지를 다음 카테고리 중 하나로 분류해주세요:
            
            1. PROPERTY_SEARCH: 부동산 매물 검색
            2. POLICY_INQUIRY: 정부 지원 정책 문의
            3. MARKET_INFO: 부동산 시장 정보 문의
            4. LOAN_CONSULTATION: 대출 상담
            5. GENERAL_CHAT: 일반 대화
            6. COMPLAINT: 불만 또는 문의사항
            
            카테고리명만 반환해주세요.
            """
            
            messages = [{"role": "user", "content": text}]
            response = await self.generate_response(messages, system_prompt)
            
            # 응답에서 카테고리만 추출
            intent = response.strip().upper()
            valid_intents = [
                "PROPERTY_SEARCH", "POLICY_INQUIRY", "MARKET_INFO",
                "LOAN_CONSULTATION", "GENERAL_CHAT", "COMPLAINT"
            ]
            
            if intent in valid_intents:
                return intent
            else:
                return "GENERAL_CHAT"  # 기본값
                
        except Exception as e:
            logger.error(f"의도 분류 실패: {str(e)}")
            return "GENERAL_CHAT"
    
    async def generate_recommendation_text(
        self, 
        user_profile: Dict[str, Any],
        matched_policies: List[Dict[str, Any]],
        recommended_properties: List[Dict[str, Any]]
    ) -> str:
        """개인맞춤형 추천 텍스트 생성"""
        try:
            system_prompt = """
            당신은 부동산 전문 상담사입니다.
            사용자의 프로필과 매칭된 정부 정책, 추천 부동산을 바탕으로
            친근하고 전문적인 추천 메시지를 작성해주세요.
            
            다음 구조로 작성해주세요:
            1. 사용자 상황 요약
            2. 적용 가능한 정부 지원 정책 설명
            3. 추천 부동산 소개 (3개 이내)
            4. 추가 조언 및 다음 단계 안내
            
            한국어로 작성하고, 존댓말을 사용해주세요.
            """
            
            # 컨텍스트 정보 구성
            context = f"""
            사용자 프로필:
            {json.dumps(user_profile, ensure_ascii=False, indent=2)}
            
            매칭된 정부 정책:
            {json.dumps(matched_policies, ensure_ascii=False, indent=2)}
            
            추천 부동산:
            {json.dumps(recommended_properties, ensure_ascii=False, indent=2)}
            """
            
            messages = [{"role": "user", "content": context}]
            response = await self.generate_response(messages, system_prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"추천 텍스트 생성 실패: {str(e)}")
            return "죄송합니다. 추천 정보를 생성하는 중 오류가 발생했습니다."
    
    async def health_check(self) -> bool:
        """Bedrock 연결 상태 확인"""
        try:
            # 간단한 테스트 호출
            test_messages = [{"role": "user", "content": "안녕하세요"}]
            response = await self.generate_response(test_messages)
            return bool(response)
            
        except Exception as e:
            logger.error(f"Bedrock 상태 확인 실패: {str(e)}")
            return False

# 전역 Bedrock 클라이언트 인스턴스
_bedrock_client = None

def get_bedrock_client() -> BedrockClient:
    """Bedrock 클라이언트 싱글톤 인스턴스 반환"""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client

async def initialize_bedrock():
    """Bedrock 클라이언트 초기화"""
    global _bedrock_client
    _bedrock_client = BedrockClient()
    
    # 연결 테스트
    is_healthy = await _bedrock_client.health_check()
    if not is_healthy:
        raise Exception("Bedrock 클라이언트 초기화 실패")
    
    logger.info("Bedrock 클라이언트 초기화 및 연결 테스트 완료")