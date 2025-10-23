"""
법정동 코드 처리 서비스 모듈
"""

import os
import re
from typing import List, Dict, Any, Optional
from collections import OrderedDict
from src.database.opensearch_client import opensearch_client
from src.utils.logger import get_logger

logger = get_logger(__name__)

class LawdService:
    """법정동 코드 처리 서비스"""
    
    def __init__(self):
        self.opensearch_client = opensearch_client
        self.lawd_codes_file = os.path.join(os.path.dirname(__file__), '..', 'lawd_codes', 'all_lawd_codes.txt')
        
    def parse_lawd_codes_file(self) -> List[Dict[str, Any]]:
        """
        법정동 코드 파일을 파싱하여 존재하는 법정동만 추출
        
        Returns:
            파싱된 법정동 코드 리스트
        """
        try:
            lawd_codes = []
            
            with open(self.lawd_codes_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 첫 번째 줄은 헤더이므로 제외
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split('\t')
                if len(parts) >= 3:
                    lawd_code = parts[0].strip()
                    lawd_name = parts[1].strip()
                    status = parts[2].strip()
                    
                    # 폐지여부가 '존재'인 경우만 처리
                    if status == '존재':
                        # 법정동 코드가 10자리인지 확인
                        if len(lawd_code) == 10 and lawd_code.isdigit():
                            # 앞 5자리 추출 (시군구 코드)
                            region_code = lawd_code[:5]
                            
                            # 3단계 레벨로 분리
                            level_1, level_2, level_3 = self._extract_three_levels(lawd_name)
                            
                            lawd_codes.append({
                                'lawd_code': region_code,
                                'level_1': level_1,
                                'level_2': level_2,
                                'level_3': level_3,
                                'exists': True
                            })
            
            logger.info(f"법정동 코드 파싱 완료: {len(lawd_codes)}개")
            return lawd_codes
            
        except Exception as e:
            logger.error(f"법정동 코드 파일 파싱 실패: {e}")
            return []
    
    def _extract_three_levels(self, lawd_name: str) -> tuple[str, str, str]:
        """
        법정동명에서 3단계 레벨로 분리
        
        Args:
            lawd_name: 법정동명 (예: "서울특별시 종로구 청운동")
            
        Returns:
            (level_1, level_2, level_3) 튜플
        """
        try:
            parts = lawd_name.split()
            
            if len(parts) == 1:
                # 시도만 있는 경우 (예: "서울특별시")
                return parts[0], None, None
            elif len(parts) == 2:
                # 시도 + 구/시/군이 있는 경우 (예: "서울특별시 종로구")
                return parts[0], parts[1], None
            elif len(parts) == 3:
                # 시도 + 구/시/군 + 동이 있는 경우 (예: "서울특별시 종로구 청운동")
                return parts[0], parts[1], parts[2]
            else:
                # 3개 이상인 경우 (예: "경기도 수원시 장안구 파장동")
                return parts[0], parts[1], parts[2] if len(parts) > 2 else None
                
        except Exception as e:
            logger.error(f"3단계 레벨 분리 실패: {e}")
            return lawd_name, None, None
    
    def create_lawd_codes_index(self) -> bool:
        """
        법정동 코드 인덱스 생성 (전체 재생성)
        
        Returns:
            인덱스 생성 성공 여부
        """
        try:
            index_name = "lawd_codes"
            
            # 인덱스 매핑 설정 (필드 순서 고정)
            mapping = {
                "mappings": {
                    "properties": OrderedDict([
                        ("lawd_code", {"type": "keyword"}),
                        ("level_1", {"type": "text", "analyzer": "korean"}),
                        ("level_2", {"type": "text", "analyzer": "korean"}),
                        ("level_3", {"type": "text", "analyzer": "korean"}),
                        ("exists", {"type": "boolean"})
                    ])
                },
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "korean": {
                                "type": "standard"
                            }
                        }
                    }
                }
            }
            
            # 기존 인덱스 강제 삭제 (전체 재생성을 위해)
            if self.opensearch_client.client.indices.exists(index=index_name):
                self.opensearch_client.client.indices.delete(index=index_name)
                logger.info(f"✅ 기존 인덱스 '{index_name}' 강제 삭제 완료")
            
            # 새 인덱스 생성
            response = self.opensearch_client.client.indices.create(index=index_name, body=mapping)
            logger.info(f"✅ 법정동 코드 인덱스 '{index_name}' 새로 생성 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 법정동 코드 인덱스 생성 실패: {e}")
            return False
    
    def load_lawd_codes_to_opensearch(self) -> bool:
        """
        법정동 코드를 OpenSearch에 로드 (전체 재생성)
        
        Returns:
            로드 성공 여부
        """
        try:
            logger.info("🔄 법정동 코드 전체 재생성 시작")
            
            # 1. 법정동 코드 파일에서 최신 데이터 파싱
            lawd_codes = self.parse_lawd_codes_file()
            if not lawd_codes:
                logger.error("❌ 파싱된 법정동 코드가 없습니다.")
                return False
            
            logger.info(f"📊 파싱된 법정동 코드: {len(lawd_codes)}개")
            
            # 2. 기존 인덱스 완전 삭제 후 새로 생성
            if not self.create_lawd_codes_index():
                logger.error("❌ 인덱스 생성 실패")
                return False
            
            # 3. 중복 제거 (같은 5자리 코드는 하나만 유지)
            unique_codes = {}
            for code in lawd_codes:
                key = code['lawd_code']
                if key not in unique_codes:
                    unique_codes[key] = code
            
            unique_lawd_codes = list(unique_codes.values())
            logger.info(f"🔄 중복 제거 후 법정동 코드: {len(unique_lawd_codes)}개")
            
            # 4. OpenSearch에 벌크 인덱싱 (필드 순서 고정)
            bulk_data = []
            for i, code in enumerate(unique_lawd_codes):
                bulk_data.append({
                    "index": {
                        "_index": "lawd_codes",
                        "_id": code['lawd_code']
                    }
                })
                # 필드 순서를 고정하여 저장
                ordered_doc = OrderedDict([
                    ("lawd_code", code['lawd_code']),
                    ("level_1", code['level_1']),
                    ("level_2", code['level_2']),
                    ("level_3", code['level_3']),
                    ("exists", code['exists'])
                ])
                bulk_data.append(ordered_doc)
            
            # 5. 벌크 인덱싱 실행
            if bulk_data:
                response = self.opensearch_client.client.bulk(body=bulk_data)
                if response.get('errors'):
                    logger.error(f"❌ 일부 법정동 코드 인덱싱 실패: {response.get('errors')}")
                    return False
                else:
                    logger.info(f"✅ 법정동 코드 {len(unique_lawd_codes)}개 전체 재생성 완료")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 법정동 코드 전체 재생성 실패: {e}")
            return False
    
    def search_lawd_codes(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        법정동 코드 검색
        
        Args:
            query: 검색 쿼리
            size: 결과 개수
            
        Returns:
            검색 결과 리스트
        """
        try:
            # 숫자로만 구성된 쿼리인 경우 정확한 매치 사용
            if query.isdigit():
                search_body = {
                    "size": size,
                    "query": {
                        "bool": {
                            "should": [
                                {"term": {"lawd_code": query}},
                                {"wildcard": {"level_1": f"*{query}*"}},
                                {"wildcard": {"level_2": f"*{query}*"}},
                                {"wildcard": {"level_3": f"*{query}*"}}
                            ]
                        }
                    }
                }
            else:
                # 텍스트 검색의 경우 여러 검색 방식 조합
                search_body = {
                    "size": size,
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["level_1^3", "level_2^2", "level_3^1"],
                                        "type": "phrase_prefix"
                                    }
                                },
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["level_1^2", "level_2", "level_3"],
                                        "type": "best_fields",
                                        "fuzziness": "AUTO"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "level_1": f"*{query}*"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "level_2": f"*{query}*"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "level_3": f"*{query}*"
                                    }
                                }
                            ]
                        }
                    }
                }
            
            response = self.opensearch_client.client.search(index="lawd_codes", body=search_body)
            
            results = []
            for hit in response['hits']['hits']:
                # 필드 순서를 고정하여 결과 생성
                result = OrderedDict([
                    ('lawd_code', hit['_source'].get('lawd_code', '')),
                    ('level_1', hit['_source'].get('level_1', '')),
                    ('level_2', hit['_source'].get('level_2', '')),
                    ('level_3', hit['_source'].get('level_3', '')),
                    ('exists', hit['_source'].get('exists', True)),
                    ('score', hit['_score'])
                ])
                results.append(result)
            
            logger.info(f"법정동 코드 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"법정동 코드 검색 실패: {e}")
            return []
    
    def get_lawd_code_info(self, lawd_code: str) -> Optional[Dict[str, Any]]:
        """
        특정 법정동 코드 정보 조회
        
        Args:
            lawd_code: 5자리 법정동 코드
            
        Returns:
            법정동 코드 정보
        """
        try:
            response = self.opensearch_client.client.get(
                index="lawd_codes", 
                id=lawd_code
            )
            
            if response['found']:
                return response['_source']
            else:
                return None
                
        except Exception as e:
            logger.error(f"법정동 코드 정보 조회 실패: {e}")
            return None
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        법정동 코드 인덱스 통계 조회
        
        Returns:
            인덱스 통계 정보
        """
        try:
            if not self.opensearch_client.client.indices.exists(index="lawd_codes"):
                return {"error": "인덱스가 존재하지 않습니다."}
            
            stats = self.opensearch_client.client.indices.stats(index="lawd_codes")
            return {
                "document_count": stats['indices']['lawd_codes']['total']['docs']['count'],
                "size": stats['indices']['lawd_codes']['total']['store']['size_in_bytes']
            }
            
        except Exception as e:
            return {"error": str(e)}
