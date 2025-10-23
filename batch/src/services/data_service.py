"""
데이터 처리 서비스 모듈
"""

from typing import Dict, List, Any
from src.config.settings import Config
from src.config.constants import DATA_TYPES
from src.utils.helpers import get_lawd_codes, get_data_type_names
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DataService:
    """데이터 처리 서비스"""
    
    def __init__(self):
        self.config = Config()
        self.data_types = DATA_TYPES
        # 법정동코드는 OpenSearch DB에서 관리됨
        
    def validate_data_type(self, data_type: str) -> bool:
        """
        데이터 타입 유효성 검사
        
        Args:
            data_type: 데이터 타입
            
        Returns:
            유효성 여부
        """
        return data_type in self.data_types
    
    def get_available_data_types(self) -> List[str]:
        """
        사용 가능한 데이터 타입 목록 반환
        
        Returns:
            데이터 타입 리스트
        """
        return list(self.data_types.keys())
    
    def get_lawd_codes_list(self) -> List[str]:
        """
        법정동코드 목록 반환
        
        Returns:
            법정동코드 리스트
        """
        return get_lawd_codes()
    
    def get_data_type_name(self, data_type: str) -> str:
        """
        데이터 타입의 한글 이름 반환
        
        Args:
            data_type: 데이터 타입
            
        Returns:
            한글 이름
        """
        return self.data_types.get(data_type, data_type)
    
    def get_lawd_code_name(self, lawd_code: str) -> str:
        """
        법정동코드의 한글 이름 반환
        
        Args:
            lawd_code: 법정동코드
            
        Returns:
            한글 이름
        """
        return self.lawd_codes.get(lawd_code, lawd_code)
    
    def process_collection_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        수집 결과 처리
        
        Args:
            results: 수집 결과
            
        Returns:
            처리된 결과
        """
        processed_results = {}
        
        for data_type, data_dict in results.items():
            if data_dict and 'clean_data' in data_dict and data_dict['clean_data'] is not None:
                df = data_dict['clean_data']
                processed_results[data_type] = {
                    'clean_data': df,  # VectorService가 기대하는 형태로 수정
                    'raw_data': data_dict.get('raw_data', []),
                    'count': len(df),
                    'type_name': self.get_data_type_name(data_type)
                }
                logger.info(f"{self.get_data_type_name(data_type)} 데이터 {len(df)}건 처리 완료")
            else:
                logger.warning(f"{self.get_data_type_name(data_type)} 데이터 없음")
                
        return processed_results
