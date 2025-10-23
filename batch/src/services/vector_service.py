"""
벡터 처리 서비스 모듈
"""

from typing import List, Dict, Any
import pandas as pd
from src.database.opensearch_client import OpenSearchClient
from src.config.constants import OPENSEARCH_INDICES
from src.utils.logger import get_logger

logger = get_logger(__name__)

class VectorService:
    """벡터 처리 서비스"""
    
    def __init__(self):
        self.opensearch_client = OpenSearchClient()
        self.indices = OPENSEARCH_INDICES
        
    def save_to_vector_db(self, results: Dict[str, Any], lawd_codes: List[str], deal_ym: str) -> bool:
        """
        벡터 데이터베이스에 저장 (기존 데이터 삭제 후 새로 저장)
        
        Args:
            results: 수집 결과
            lawd_codes: 법정동코드 리스트
            deal_ym: 거래년월
            
        Returns:
            저장 성공 여부
        """
        try:
            total_documents = 0
            
            for data_type, data_dict in results.items():
                if not data_dict or 'clean_data' not in data_dict or data_dict['clean_data'] is None:
                    continue
                    
                df = data_dict['clean_data']
                if len(df) == 0:
                    continue
                
                # 인덱스 이름 가져오기
                index_name = self.indices.get(data_type, f"{data_type}_data")
                
                # 기존 데이터 삭제 (동일 조건)
                self._delete_existing_data(index_name, data_type, lawd_codes, deal_ym)
                
                # 문서 형태로 변환
                documents = self._prepare_documents(df, data_type, lawd_codes, deal_ym)
                
                # OpenSearch에 저장
                success = self.opensearch_client.add_documents(index_name, documents)
                
                if success:
                    total_documents += len(documents)
                    logger.info(f"{data_type} 데이터 {len(documents)}개 문서 저장 완료")
                else:
                    logger.error(f"{data_type} 데이터 저장 실패")
                    
            logger.info(f"총 {total_documents}개 문서 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"벡터 데이터베이스 저장 중 오류: {e}")
            return False
    
    def _delete_existing_data(self, index_name: str, data_type: str, lawd_codes: List[str], deal_ym: str) -> bool:
        """
        기존 데이터 삭제 (동일 조건)
        
        Args:
            index_name: 인덱스 이름
            data_type: 데이터 타입
            lawd_codes: 법정동코드 리스트
            deal_ym: 거래년월
            
        Returns:
            삭제 성공 여부
        """
        try:
            # 인덱스가 존재하지 않으면 삭제할 데이터가 없음
            if not self.opensearch_client.client.indices.exists(index=index_name):
                logger.info(f"{index_name} 인덱스가 존재하지 않습니다.")
                return True
            
            # 삭제 쿼리 구성 (동일 조건의 데이터만 삭제)
            delete_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"data_type": data_type}},
                            {"term": {"deal_ymd": deal_ym}}
                        ]
                    }
                }
            }
            
            # 법정동코드 조건 추가 (단일 값으로 변경)
            if lawd_codes:
                delete_query["query"]["bool"]["must"].append({"term": {"lawd_code": lawd_codes[0]}})
            
            # 삭제 실행
            response = self.opensearch_client.client.delete_by_query(
                index=index_name,
                body=delete_query
            )
            
            deleted_count = response.get('deleted', 0)
            if deleted_count > 0:
                logger.info(f"{index_name}에서 {deleted_count}개 문서 삭제 완료 (조건: {data_type}, {lawd_codes}, {deal_ym})")
            else:
                logger.info(f"{index_name}에서 삭제할 문서가 없습니다 (조건: {data_type}, {lawd_codes}, {deal_ym})")
            
            return True
            
        except Exception as e:
            logger.error(f"기존 데이터 삭제 중 오류: {e}")
            return False
    
    def _prepare_documents(self, df, data_type: str, lawd_codes: List[str], deal_ym: str) -> List[Dict[str, Any]]:
        """
        문서 형태로 변환
        
        Args:
            df: 데이터프레임
            data_type: 데이터 타입
            lawd_codes: 법정동코드 리스트
            deal_ym: 거래년월
            
        Returns:
            문서 리스트
        """
        documents = []
        
        for idx, row in df.iterrows():
            # 문서 ID 생성
            doc_id = f"{data_type}_{lawd_codes[0] if lawd_codes else 'unknown'}_{deal_ym}_{idx}"
            
            # 콘텐츠 생성 (검색용)
            content_parts = []
            for col in df.columns:
                if col in ['apartment_name', 'building_name', 'apt_name'] and pd.notna(row[col]):
                    content_parts.append(str(row[col]))
                elif col in ['deal_amount', 'rent_amount'] and pd.notna(row[col]):
                    content_parts.append(f"{row[col]}만원")
                elif col in ['area', 'exclusive_area'] and pd.notna(row[col]):
                    content_parts.append(f"{row[col]}㎡")
                    
            content = " ".join(content_parts)
            
            # 문서 생성
            doc = {
                'id': doc_id,
                'data_type': data_type,
                'lawd_code': lawd_codes[0] if lawd_codes else 'unknown',  # 단일 값으로 변경
                'deal_ymd': deal_ym,
                'content': content,
                'metadata': row.to_dict()
            }
            
            documents.append(doc)
            
        return documents
    
    def search_similar_documents(self, query: str, data_type: str = None, size: int = 10) -> List[Dict[str, Any]]:
        """
        유사 문서 검색
        
        Args:
            query: 검색 쿼리
            data_type: 데이터 타입 (선택사항)
            size: 반환할 문서 수
            
        Returns:
            검색 결과
        """
        try:
            index_name = self.indices.get(data_type, f"{data_type}_data") if data_type else None
            return self.opensearch_client.search(index_name, query, size, data_type)
        except Exception as e:
            logger.error(f"문서 검색 중 오류: {e}")
            return []
