"""
OpenSearch 클라이언트 모듈
OpenSearch를 사용하여 벡터 데이터를 저장하고 검색합니다.
"""

import os
import json
import sys
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 직접 config.py import
import importlib.util
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.py')
spec = importlib.util.spec_from_file_location("config", config_path)
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)
Config = config_module.Config


class OpenSearchClient:
    """무료 OpenSearch 클라이언트"""
    
    def __init__(self):
        self.client = self._create_client()
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    def _create_client(self) -> OpenSearch:
        """OpenSearch 클라이언트 생성"""
        try:
            # OpenSearch 클라이언트 생성
            client = OpenSearch(
                hosts=[Config.OPENSEARCH_ENDPOINT],
                http_auth=(Config.OPENSEARCH_USERNAME, Config.OPENSEARCH_PASSWORD),
                use_ssl=False,  # 로컬 환경에서는 SSL 비활성화
                verify_certs=False,
                timeout=30
            )
            
            print("✅ OpenSearch 클라이언트 연결 성공")
            return client
            
        except Exception as e:
            print(f"❌ OpenSearch 클라이언트 연결 실패: {e}")
            raise
    
    def create_index(self, index_name: str, vector_dim: int = 384) -> bool:
        """인덱스 생성"""
        try:
            # 인덱스가 이미 존재하는지 확인
            if self.client.indices.exists(index=index_name):
                print(f"📋 인덱스 '{index_name}'가 이미 존재합니다.")
                return True
            
            # 인덱스 매핑 설정
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "data_type": {"type": "keyword"},
                        "lawd_code": {"type": "keyword"},
                        "deal_ymd": {"type": "keyword"},
                        "content": {"type": "text"},
                        "metadata": {"type": "object"},
                        "vector": {
                            "type": "knn_vector",
                            "dimension": vector_dim,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        }
                    }
                },
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                }
            }
            
            # 인덱스 생성
            response = self.client.indices.create(index=index_name, body=mapping)
            print(f"✅ 인덱스 '{index_name}' 생성 완료")
            return True
            
        except Exception as e:
            print(f"❌ 인덱스 생성 실패: {e}")
            return False
    
    def get_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"❌ 임베딩 생성 실패: {e}")
            return []
    
    def add_documents(self, index_name: str, documents: List[Dict[str, Any]]) -> bool:
        """문서들을 인덱스에 추가"""
        try:
            # 인덱스 생성 확인
            if not self.client.indices.exists(index=index_name):
                self.create_index(index_name)
            
            # 벡터 임베딩 생성 및 문서 준비
            bulk_data = []
            for doc in documents:
                # 텍스트 임베딩 생성
                content = doc.get('content', '')
                if content:
                    vector = self.get_embedding(content)
                    if vector:
                        doc['vector'] = vector
                
                # OpenSearch 문서 형식으로 변환
                bulk_data.append({
                    "index": {
                        "_index": index_name,
                        "_id": doc.get('id')
                    }
                })
                bulk_data.append(doc)
            
            # 벌크 인덱싱
            if bulk_data:
                response = self.client.bulk(body=bulk_data)
                if response.get('errors'):
                    print(f"⚠️  일부 문서 인덱싱 실패: {response.get('errors')}")
                else:
                    print(f"✅ {len(documents)}개 문서 인덱싱 완료")
                return True
            
        except Exception as e:
            print(f"❌ 문서 추가 실패: {e}")
            return False
    
    def search(self, index_name: str, query: str, size: int = 10, 
               data_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """벡터 검색 수행"""
        try:
            # 쿼리 임베딩 생성
            query_vector = self.get_embedding(query)
            if not query_vector:
                return []
            
            # 검색 쿼리 구성
            search_body = {
                "size": size,
                "query": {
                    "knn": {
                        "vector": {
                            "vector": query_vector,
                            "k": size
                        }
                    }
                }
            }
            
            # 데이터 타입 필터 추가
            if data_type:
                search_body["query"] = {
                    "bool": {
                        "must": [
                            {"knn": {"vector": {"vector": query_vector, "k": size}}}
                        ],
                        "filter": [
                            {"term": {"data_type": data_type}}
                        ]
                    }
                }
            
            # 검색 실행
            response = self.client.search(index=index_name, body=search_body)
            
            results = []
            for hit in response['hits']['hits']:
                result = {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'content': hit['_source'].get('content', ''),
                    'metadata': hit['_source'].get('metadata', {}),
                    'data_type': hit['_source'].get('data_type', ''),
                    'lawd_cd': hit['_source'].get('lawd_cd', ''),
                    'deal_ymd': hit['_source'].get('deal_ymd', '')
                }
                results.append(result)
            
            print(f"🔍 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            print(f"❌ 검색 실패: {e}")
            return []
    
    def delete_index(self, index_name: str) -> bool:
        """인덱스 삭제"""
        try:
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                print(f"✅ 인덱스 '{index_name}' 삭제 완료")
                return True
            else:
                print(f"⚠️  인덱스 '{index_name}'가 존재하지 않습니다.")
                return True
        except Exception as e:
            print(f"❌ 인덱스 삭제 실패: {e}")
            return False
    
    def get_index_info(self, index_name: str) -> Dict[str, Any]:
        """인덱스 정보 조회"""
        try:
            if not self.client.indices.exists(index=index_name):
                return {"error": "인덱스가 존재하지 않습니다."}
            
            stats = self.client.indices.stats(index=index_name)
            return {
                "document_count": stats['indices'][index_name]['total']['docs']['count'],
                "size": stats['indices'][index_name]['total']['store']['size_in_bytes']
            }
        except Exception as e:
            return {"error": str(e)}


# 전역 클라이언트 인스턴스
opensearch_client = OpenSearchClient()
