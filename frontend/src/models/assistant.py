"""
부동산 AI 어시스턴트 모델
"""

from typing import Dict, Any
from ..utils.aws_knowledge_base import AWSKnowledgeBase, format_retrieval_results
from ..utils.data_loader import S3DataLoader


class RealEstateAssistant:
    """부동산 데이터 AI 어시스턴트 클래스"""
    
    def __init__(self, region_name: str = "ap-northeast-2"):
        self.kb_client = AWSKnowledgeBase(region_name)
        self.data_loader = S3DataLoader(region_name=region_name)
        
    def query_knowledge_base(self, query: str, knowledge_base_id: str, max_results: int = 5, search_type: str = "hybrid") -> Dict[str, Any]:
        """AWS Knowledge Base에서 데이터 검색"""
        if search_type == "vector":
            return self.kb_client.retrieve_vector_search(knowledge_base_id, query, max_results)
        if search_type == "keyword":
            return self.kb_client.retrieve_keyword_search(knowledge_base_id, query, max_results)
        # 기본값: 하이브리드
        return self.kb_client.retrieve_hybrid_search(knowledge_base_id, query, max_results)
    
    def generate_response(self, query: str, context: str, model_id: str = None) -> str:
        """Claude 모델을 사용하여 응답 생성"""
        return self.kb_client.generate_response(query, context, model_id)
    
    def get_data_summary(self, data_type: str, lawd_cd: str) -> Dict[str, Any]:
        """데이터 요약 정보 조회"""
        return self.data_loader.get_data_summary(data_type, lawd_cd)
