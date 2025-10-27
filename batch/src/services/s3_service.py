"""
S3 서비스 모듈
OpenSearch 데이터 수집 시 S3에 CSV 형태로 데이터를 저장하는 기능을 제공합니다.
"""

import os
import io
import pandas as pd
import boto3
from typing import Dict, Any, Optional
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from src.utils.logger import get_logger
from src.config.constants import OPENSEARCH_INDICES

logger = get_logger(__name__)


class S3Service:
    """S3 데이터 저장 서비스"""
    
    def __init__(self, bucket_name: str = "bds-collect", region_name: str = "ap-northeast-2"):
        """
        S3 서비스 초기화
        
        Args:
            bucket_name: S3 버킷 이름
            region_name: AWS 리전
        """
        self.bucket_name = bucket_name
        self.region_name = region_name
        
        # AWS 자격 증명 설정
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        # S3 클라이언트 초기화
        try:
            if self.aws_access_key_id and self.aws_secret_access_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.region_name
                )
            else:
                # IAM 역할 또는 기본 자격 증명 사용
                self.s3_client = boto3.client('s3', region_name=self.region_name)
            
            logger.info(f"S3 서비스 초기화 완료 - 버킷: {bucket_name}, 리전: {region_name}")
            
        except NoCredentialsError:
            logger.error("AWS 자격 증명을 찾을 수 없습니다.")
            self.s3_client = None
        except Exception as e:
            logger.error(f"S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None
    
    def save_dataframe_to_s3(self, df: pd.DataFrame, data_type: str, lawd_cd: str, deal_ym: str, 
                            data_category: str = "clean") -> Optional[str]:
        """
        DataFrame을 CSV 형태로 S3에 저장
        
        Args:
            df: 저장할 DataFrame
            data_type: 데이터 타입 (apartment, offi, rh)
            lawd_cd: 법정동 코드
            deal_ym: 거래년월 (YYYYMM)
            data_category: 데이터 카테고리 (clean, raw)
            
        Returns:
            저장된 S3 객체 키 또는 None
        """
        if self.s3_client is None:
            logger.error("S3 클라이언트가 초기화되지 않았습니다.")
            return None
        
        if df is None or len(df) == 0:
            logger.warning("저장할 데이터가 없습니다.")
            return None
        
        try:
            # S3 객체 키 생성: data/{data_type}/{lawd_cd}/{year}/{month}/{data_category}_{date}.csv
            year = deal_ym[:4]
            month = deal_ym[4:6]
            date = datetime.now().strftime("%Y%m%d")
            
            s3_key = f"data/{data_type}/{lawd_cd}/{year}/{month}/{data_category}_{date}.csv"
            
            # DataFrame을 CSV 형태로 메모리에 저장
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_content = csv_buffer.getvalue()
            
            # S3에 업로드
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=csv_content.encode('utf-8'),
                ContentType='text/csv; charset=utf-8',
                Metadata={
                    'data_type': data_type,
                    'lawd_cd': lawd_cd,
                    'deal_ym': deal_ym,
                    'data_category': data_category,
                    'record_count': str(len(df)),
                    'upload_time': datetime.now().isoformat()
                }
            )
            
            logger.info(f"S3 저장 완료: s3://{self.bucket_name}/{s3_key} ({len(df)}개 레코드)")
            return s3_key
            
        except ClientError as e:
            logger.error(f"S3 업로드 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"S3 저장 중 오류: {e}")
            return None
    
    def save_collection_results_to_s3(self, results: Dict[str, Any], lawd_codes: list, deal_ym: str) -> Dict[str, str]:
        """
        수집 결과를 S3에 저장
        
        Args:
            results: 수집 결과 딕셔너리
            lawd_codes: 법정동 코드 리스트
            deal_ym: 거래년월
            
        Returns:
            저장된 S3 객체 키들의 딕셔너리
        """
        saved_keys = {}
        
        if not results:
            logger.warning("저장할 결과가 없습니다.")
            return saved_keys
        
        for data_type, data_dict in results.items():
            if not data_dict or 'clean_data' not in data_dict or data_dict['clean_data'] is None:
                continue
            
            df = data_dict['clean_data']
            if len(df) == 0:
                continue
            
            # 정제된 데이터 저장
            clean_key = self.save_dataframe_to_s3(
                df, data_type, lawd_codes[0], deal_ym, "clean"
            )
            if clean_key:
                saved_keys[f"{data_type}_clean"] = clean_key
            
            # 원본 데이터가 있으면 저장
            if 'raw_data' in data_dict and data_dict['raw_data'] is not None:
                raw_df = data_dict['raw_data']
                if len(raw_df) > 0:
                    raw_key = self.save_dataframe_to_s3(
                        raw_df, data_type, lawd_codes[0], deal_ym, "raw"
                    )
                    if raw_key:
                        saved_keys[f"{data_type}_raw"] = raw_key
        
        return saved_keys
    
    def check_bucket_exists(self) -> bool:
        """
        S3 버킷 존재 여부 확인
        
        Returns:
            버킷 존재 여부
        """
        if self.s3_client is None:
            return False
        
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"S3 버킷 '{self.bucket_name}'이 존재하지 않습니다.")
            else:
                logger.error(f"S3 버킷 확인 중 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"S3 버킷 확인 중 오류: {e}")
            return False
    
    def create_bucket_if_not_exists(self) -> bool:
        """
        S3 버킷이 없으면 생성
        
        Returns:
            생성 성공 여부
        """
        if self.s3_client is None:
            return False
        
        try:
            # 버킷 존재 확인
            if self.check_bucket_exists():
                logger.info(f"S3 버킷 '{self.bucket_name}'이 이미 존재합니다.")
                return True
            
            # 버킷 생성
            if self.region_name == 'us-east-1':
                # us-east-1은 LocationConstraint가 필요하지 않음
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region_name}
                )
            
            logger.info(f"S3 버킷 '{self.bucket_name}' 생성 완료")
            return True
            
        except ClientError as e:
            logger.error(f"S3 버킷 생성 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"S3 버킷 생성 중 오류: {e}")
            return False
