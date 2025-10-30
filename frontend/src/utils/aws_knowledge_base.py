"""
AWS Knowledge Base 연결 및 관리 유틸리티
"""

import boto3
import json
import logging
from typing import List, Dict, Any, Optional
import os
from botocore.exceptions import ClientError, NoCredentialsError

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AWSKnowledgeBase:
    """AWS Knowledge Base 연결 및 관리 클래스"""
    
    def __init__(self, region_name: str = "ap-northeast-2"):
        self.region_name = region_name
        
        try:
            self.bedrock_agent_runtime = boto3.client(
                'bedrock-agent-runtime',
                region_name=region_name
            )
            self.bedrock_runtime = boto3.client(
                'bedrock-runtime',
                region_name=region_name
            )
            logger.info(f"AWS Knowledge Base 클라이언트 초기화 완료 - 리전: {region_name}")
        except NoCredentialsError:
            logger.error("AWS 자격 증명을 찾을 수 없습니다.")
            self.bedrock_agent_runtime = None
            self.bedrock_runtime = None
        except Exception as e:
            logger.error(f"AWS 클라이언트 초기화 실패: {str(e)}")
            self.bedrock_agent_runtime = None
            self.bedrock_runtime = None
    
    def retrieve_documents(self, knowledge_base_id: str, query: str, 
                          max_results: int = 10, search_type: str = "hybrid") -> Dict[str, Any]:
        """Knowledge Base에서 문서 검색 (하이브리드 검색 지원)
        
        Args:
            knowledge_base_id: Knowledge Base ID
            query: 검색 쿼리
            max_results: 최대 결과 수
            search_type: 검색 타입 ("vector", "keyword", "hybrid")
        """
        if not self.bedrock_agent_runtime:
            logger.error("AWS 클라이언트가 초기화되지 않았습니다.")
            return {"error": "AWS 클라이언트가 초기화되지 않았습니다."}
        
        logger.info(f"Knowledge Base 검색 시작 - ID: {knowledge_base_id}, 쿼리: {query[:50]}..., 타입: {search_type}")
        
        try:
            # 검색 설정 구성: 사이드바 선택(search_type)에 따라 동적으로 지정
            # Bedrock KB의 overrideSearchType은 'HYBRID' 또는 'SEMANTIC'를 사용
            if search_type == "vector":
                override_type = 'SEMANTIC'
            else:
                # "hybrid" 및 그 외 기본값은 HYBRID로 처리
                override_type = 'HYBRID'

            retrieval_config = {
                'vectorSearchConfiguration': {
                    'overrideSearchType': override_type,
                    'numberOfResults': max_results
                }
            }
            
            # 하이브리드 검색의 경우 더 많은 결과를 가져와서 후처리
            if search_type == "hybrid":
                # 하이브리드 검색을 위해 더 많은 결과를 가져오기
                retrieval_config['vectorSearchConfiguration']['numberOfResults'] = max_results * 2
            
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration=retrieval_config
            )
            # 하이브리드 검색 결과 처리 (벡터 검색 결과를 다양화)
            if search_type == "hybrid":
                response = self._process_hybrid_results(response, max_results, query)
            
            logger.info(f"Knowledge Base 검색 성공 - {len(response.get('retrievalResults', []))}개 결과")
            
            # 검색 결과 상세 로그
            if 'retrievalResults' in response:
                for i, result in enumerate(response['retrievalResults'], 1):
                    score = result.get('score', 0)
                    content = result.get('content', {})
                    text = content.get('text', '')[:100] + '...' if len(content.get('text', '')) > 100 else content.get('text', '')
                    location = result.get('location', {})
                    search_type_result = result.get('searchType', 'unknown')
                    
                    logger.info(f"  결과 {i}: 신뢰도={score:.3f}, 타입={search_type_result}, 내용='{text}', 위치={location}")
            else:
                logger.warning("검색 결과에 'retrievalResults' 키가 없습니다.")
            
            return response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error'].get('Message', '알 수 없는 오류')
            
            logger.error(f"Knowledge Base 검색 실패 [{error_code}]: {error_message}")
            
            if error_code == 'ResourceNotFoundException':
                return {"error": f"Knowledge Base를 찾을 수 없습니다: {knowledge_base_id} (오류: {error_message})"}
            elif error_code == 'AccessDeniedException':
                return {"error": f"Knowledge Base에 접근할 권한이 없습니다. (오류: {error_message})"}
            elif error_code == 'ValidationException':
                return {"error": f"요청 파라미터가 올바르지 않습니다. (오류: {error_message})"}
            elif error_code == 'ThrottlingException':
                return {"error": f"요청이 너무 많습니다. 잠시 후 다시 시도해주세요. (오류: {error_message})"}
            else:
                return {"error": f"Knowledge Base 검색 오류 [{error_code}]: {error_message}"}
        except Exception as e:
            logger.error(f"Knowledge Base 검색 중 예상치 못한 오류: {str(e)}")
            return {"error": f"예상치 못한 오류: {str(e)}"}
    
    def _process_hybrid_results(self, response: Dict[str, Any], max_results: int, query: str) -> Dict[str, Any]:
        """하이브리드 검색 결과 처리 및 다양화"""
        if 'retrievalResults' not in response:
            return response
        
        results = response['retrievalResults']
        
        # 중복 제거를 위한 딕셔너리 (내용 기반)
        unique_results = {}
        
        for result in results:
            content = result.get('content', {})
            text = content.get('text', '')
            
            # 텍스트 내용을 키로 사용하여 중복 제거
            if text and text not in unique_results:
                # 검색 타입 정보 추가
                result['searchType'] = 'hybrid'
                unique_results[text] = result
        
        # 하이브리드 점수 계산 (신뢰도 + 키워드 매칭 보너스)
        for result in unique_results.values():
            base_score = result.get('score', 0)
            text = result.get('content', {}).get('text', '').lower()
            query_lower = query.lower()
            
            # 키워드 매칭 보너스 계산
            keyword_bonus = 0
            query_words = query_lower.split()
            for word in query_words:
                if word in text:
                    keyword_bonus += 0.1
            
            # 하이브리드 점수 = 기본 점수 + 키워드 보너스
            result['hybridScore'] = base_score + keyword_bonus
        
        # 하이브리드 점수로 정렬
        sorted_results = sorted(unique_results.values(), 
                              key=lambda x: x.get('hybridScore', 0), 
                              reverse=True)
        
        # 최대 결과 수만큼 제한
        final_results = sorted_results[:max_results]
        
        logger.info(f"하이브리드 검색 결과 처리: {len(results)}개 -> {len(final_results)}개 (다양화 후)")
        
        return {
            'retrievalResults': final_results,
            'nextToken': response.get('nextToken'),
            'queryId': response.get('queryId')
        }
    
    def retrieve_vector_search(self, knowledge_base_id: str, query: str, 
                             max_results: int = 5) -> Dict[str, Any]:
        """벡터 검색만 수행"""
        return self.retrieve_documents(knowledge_base_id, query, max_results, "vector")
    
    def retrieve_keyword_search(self, knowledge_base_id: str, query: str, 
                              max_results: int = 5) -> Dict[str, Any]:
        """키워드 검색 시뮬레이션 (벡터 검색 + 키워드 보너스)"""
        # 키워드 검색을 위해 더 많은 결과를 가져와서 키워드 매칭으로 필터링
        results = self.retrieve_documents(knowledge_base_id, query, max_results * 2, "vector")
        
        if 'retrievalResults' not in results:
            return results
        
        # 키워드 매칭 점수로 재정렬
        for result in results['retrievalResults']:
            text = result.get('content', {}).get('text', '').lower()
            query_lower = query.lower()
            
            # 키워드 매칭 점수 계산
            keyword_score = 0
            query_words = query_lower.split()
            for word in query_words:
                if word in text:
                    keyword_score += 1
            
            result['keywordScore'] = keyword_score
            result['searchType'] = 'keyword'
        
        # 키워드 점수로 정렬
        results['retrievalResults'] = sorted(
            results['retrievalResults'], 
            key=lambda x: x.get('keywordScore', 0), 
            reverse=True
        )[:max_results]
        
        return results
    
    def retrieve_hybrid_search(self, knowledge_base_id: str, query: str, 
                             max_results: int = 5) -> Dict[str, Any]:
        """하이브리드 검색 수행 (벡터 + 키워드)"""
        return self.retrieve_documents(knowledge_base_id, query, max_results, "hybrid")
    
    def generate_response(self, query: str, context: str, 
                         model_id: str = None) -> str:
        """Claude 모델을 사용하여 응답 생성"""
        if not self.bedrock_runtime:
            logger.error("AWS Bedrock 클라이언트가 초기화되지 않았습니다.")
            return "AWS Bedrock 클라이언트가 초기화되지 않았습니다."
        
        # 환경변수에서 모델 ID 또는 Inference Profile ID 가져오기
        if model_id is None:
            # Inference Profile 우선 사용
            inference_profile_id = os.getenv("BEDROCK_INFERENCE_PROFILE_ID")
            if inference_profile_id:
                model_id = inference_profile_id
                logger.info(f"Inference Profile 사용: {model_id}")
            else:
                # Inference Profile이 없으면 일반 모델 ID 사용
                model_id = os.getenv("BEDROCK_MODEL_ID")
                if not model_id:
                    logger.error("BEDROCK_MODEL_ID 또는 BEDROCK_INFERENCE_PROFILE_ID 환경변수가 설정되지 않았습니다.")
                    return "❌ BEDROCK_MODEL_ID 또는 BEDROCK_INFERENCE_PROFILE_ID 환경변수가 설정되지 않았습니다. .env 파일에서 설정해주세요."
        
        logger.info(f"Claude 모델 응답 생성 시작 - 모델: {model_id}")
        
        try:
            prompt = f"""
당신은 부동산 전문 AI 어시스턴트입니다. 
사용자의 질문에 대해 제공된 부동산 및 정책 데이터를 바탕으로 정확하고 도움이 되는 답변을 제공해주세요.

사용자 질문: {query}

참고 데이터:
{context}

답변 시 다음 사항을 고려해주세요:
1. 데이터에 기반한 정확한 정보 제공
2. 구체적인 수치와 지역 정보 포함
3. 시장 동향이나 패턴 분석
4. 추가 조사가 필요한 경우 안내
5. 한국어로 자연스럽게 답변

답변:
"""
            
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            result = json.loads(response['body'].read())
            response_text = result['content'][0]['text']
            
            logger.info(f"Claude 모델 응답 생성 성공 - 응답 길이: {len(response_text)}자")
            logger.info(f"응답 미리보기: {response_text[:200]}...")
            
            return response_text
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error'].get('Message', '알 수 없는 오류')
            
            logger.error(f"Claude 모델 응답 생성 실패 [{error_code}]: {error_message}")
            
            if error_code == 'AccessDeniedException':
                return f"**AccessDeniedException**: AWS Bedrock에 접근할 권한이 없습니다.\n\n**상세 오류**: {error_message}\n\n**해결방법**: AWS IAM에서 Bedrock 권한을 확인해주세요."
            elif error_code == 'ValidationException':
                return f"**ValidationException**: 모델 ID가 올바르지 않습니다.\n\n**상세 오류**: {error_message}\n\n**해결방법**: 올바른 모델 ID를 사용하거나 Inference Profile을 사용해주세요."
            elif error_code == 'ResourceNotFoundException':
                return f"**ResourceNotFoundException**: 요청한 리소스를 찾을 수 없습니다.\n\n**상세 오류**: {error_message}\n\n**해결방법**: 모델 ID나 리전 설정을 확인해주세요."
            elif error_code == 'ThrottlingException':
                return f"**ThrottlingException**: 요청이 너무 많습니다.\n\n**상세 오류**: {error_message}\n\n**해결방법**: 잠시 후 다시 시도해주세요."
            else:
                return f"**{error_code}**: Bedrock 응답 생성 오류\n\n**상세 오류**: {error_message}"
        except Exception as e:
            logger.error(f"Claude 모델 응답 생성 중 예상치 못한 오류: {str(e)}")
            return f"응답 생성 중 오류: {str(e)}"
    
    def get_knowledge_base_info(self, knowledge_base_id: str) -> Dict[str, Any]:
        """Knowledge Base 정보 조회"""
        logger.info(f"Knowledge Base 정보 조회 시작 - ID: {knowledge_base_id}")
        
        try:
            bedrock_agent = boto3.client('bedrock-agent', region_name=self.region_name)
            
            response = bedrock_agent.get_knowledge_base(
                knowledgeBaseId=knowledge_base_id
            )
            
            logger.info("Knowledge Base 정보 조회 성공")
            return {
                "name": response.get('knowledgeBase', {}).get('name', ''),
                "status": response.get('knowledgeBase', {}).get('status', ''),
                "description": response.get('knowledgeBase', {}).get('description', ''),
                "created_at": response.get('knowledgeBase', {}).get('createdAt', ''),
                "updated_at": response.get('knowledgeBase', {}).get('updatedAt', '')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error'].get('Message', '알 수 없는 오류')
            logger.error(f"Knowledge Base 정보 조회 실패 [{error_code}]: {error_message}")
            return {"error": f"Knowledge Base 정보 조회 오류 [{error_code}]: {error_message}"}
        except Exception as e:
            logger.error(f"Knowledge Base 정보 조회 중 예상치 못한 오류: {str(e)}")
            return {"error": f"예상치 못한 오류: {str(e)}"}

def format_retrieval_results(results: Dict[str, Any]) -> str:
    """검색 결과를 포맷팅하여 반환"""
    if "error" in results:
        return f"오류: {results['error']}"
    
    if 'retrievalResults' not in results:
        return "검색 결과가 없습니다."
    
    formatted_results = []
    for i, result in enumerate(results['retrievalResults'], 1):
        content = result.get('content', {})
        text = content.get('text', '')
        score = result.get('score', 0)
        
        formatted_results.append(f"""
**결과 {i}** (신뢰도: {score:.2f})
{text}
---
""")
    
    return "\n".join(formatted_results)
