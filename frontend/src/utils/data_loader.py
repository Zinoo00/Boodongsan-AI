"""
S3에서 부동산 데이터를 로드하는 유틸리티
"""

import boto3
import pandas as pd
import io
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os
from botocore.exceptions import ClientError, NoCredentialsError

class S3DataLoader:
    """S3에서 부동산 데이터를 로드하는 클래스"""
    
    def __init__(self, bucket_name: str = "bds-collect", region_name: str = "ap-northeast-2"):
        self.bucket_name = bucket_name
        self.region_name = region_name
        
        try:
            self.s3_client = boto3.client('s3', region_name=region_name)
        except NoCredentialsError:
            print("AWS 자격 증명을 찾을 수 없습니다.")
            self.s3_client = None
    
    def list_data_files(self, data_type: str = None, lawd_cd: str = None, 
                       year: str = None, month: str = None) -> List[Dict[str, Any]]:
        """S3에서 데이터 파일 목록 조회"""
        if not self.s3_client:
            return []
        
        try:
            prefix = "data/"
            if data_type:
                prefix += f"{data_type}/"
            if lawd_cd:
                prefix += f"{lawd_cd}/"
            if year:
                prefix += f"{year}/"
            if month:
                prefix += f"{month}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.csv'):
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'path_parts': obj['Key'].split('/')
                        })
            
            return files
            
        except ClientError as e:
            print(f"S3 파일 목록 조회 오류: {e}")
            return []
    
    def load_csv_from_s3(self, s3_key: str) -> Optional[pd.DataFrame]:
        """S3에서 CSV 파일 로드"""
        if not self.s3_client:
            return None
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            csv_content = response['Body'].read().decode('utf-8')
            
            # StringIO를 사용하여 CSV 읽기
            df = pd.read_csv(io.StringIO(csv_content))
            return df
            
        except ClientError as e:
            print(f"S3 파일 로드 오류 ({s3_key}): {e}")
            return None
    
    def load_recent_data(self, data_type: str, lawd_cd: str, 
                        days_back: int = 30) -> Optional[pd.DataFrame]:
        """최근 N일간의 데이터 로드"""
        if not self.s3_client:
            return None
        
        try:
            # 최근 파일들 조회
            files = self.list_data_files(data_type, lawd_cd)
            
            if not files:
                return None
            
            # 날짜별로 정렬 (최신순)
            files.sort(key=lambda x: x['last_modified'], reverse=True)
            
            # 최근 파일들 로드
            recent_files = files[:5]  # 최근 5개 파일
            dataframes = []
            
            for file_info in recent_files:
                df = self.load_csv_from_s3(file_info['key'])
                if df is not None:
                    # 파일 경로에서 날짜 정보 추출
                    path_parts = file_info['path_parts']
                    if len(path_parts) >= 4:
                        year = path_parts[2]
                        month = path_parts[3]
                        df['수집년월'] = f"{year}{month}"
                    
                    dataframes.append(df)
            
            if dataframes:
                # 모든 데이터프레임 합치기
                combined_df = pd.concat(dataframes, ignore_index=True)
                return combined_df
            
            return None
            
        except Exception as e:
            print(f"최근 데이터 로드 오류: {e}")
            return None
    
    def get_available_years_months(self, data_type: str, lawd_cd: str) -> Dict[str, List[str]]:
        """사용 가능한 년월 목록 조회"""
        if not self.s3_client:
            return {'years': [], 'months': {}}
        
        try:
            prefix = f"data/{data_type}/{lawd_cd}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            
            years = []
            months_by_year = {}
            
            # 년도 목록 조회
            if 'CommonPrefixes' in response:
                for prefix_info in response['CommonPrefixes']:
                    year_path = prefix_info['Prefix']
                    year = year_path.replace(prefix, '').rstrip('/')
                    if year.isdigit() and len(year) == 4:
                        years.append(year)
            
            # 각 년도의 월 목록 조회
            for year in years:
                year_prefix = f"{prefix}{year}/"
                year_response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=year_prefix,
                    Delimiter='/'
                )
                
                months = []
                if 'CommonPrefixes' in year_response:
                    for prefix_info in year_response['CommonPrefixes']:
                        month_path = prefix_info['Prefix']
                        month = month_path.replace(year_prefix, '').rstrip('/')
                        if month.isdigit() and 1 <= int(month) <= 12:
                            months.append(month)
                
                months_by_year[year] = sorted(months)
            
            return {
                'years': sorted(years),
                'months': months_by_year
            }
            
        except ClientError as e:
            print(f"S3 년월 목록 조회 오류: {e}")
            return {'years': [], 'months': {}}
    
    def get_data_summary(self, data_type: str, lawd_cd: str) -> Dict[str, Any]:
        """데이터 요약 정보 조회"""
        files = self.list_data_files(data_type, lawd_cd)
        
        if not files:
            return {
                'total_files': 0,
                'total_size': 0,
                'latest_file': None,
                'date_range': None
            }
        
        # 파일 크기 합계
        total_size = sum(file['size'] for file in files)
        
        # 최신 파일
        latest_file = max(files, key=lambda x: x['last_modified'])
        
        # 날짜 범위
        dates = [file['last_modified'].date() for file in files]
        date_range = {
            'earliest': min(dates) if dates else None,
            'latest': max(dates) if dates else None
        }
        
        return {
            'total_files': len(files),
            'total_size': total_size,
            'latest_file': latest_file['key'],
            'date_range': date_range
        }

    def load_latest_data(self, data_type: str, lawd_cd: str, max_files: int = 10) -> Optional[pd.DataFrame]:
        """S3에서 최신 데이터를 로드 (여러 파일 통합)"""
        if not self.s3_client:
            return None
        
        try:
            # 최신 데이터 파일들 찾기
            prefix = f"data/{data_type}/{lawd_cd}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return None
            
            # 파일을 날짜순으로 정렬하여 최신 파일들 찾기
            files = []
            for obj in response['Contents']:
                if obj['Key'].endswith('.csv'):
                    files.append({
                        'key': obj['Key'],
                        'last_modified': obj['LastModified'],
                        'path_parts': obj['Key'].split('/')
                    })
            
            if not files:
                return None
            
            # 최신 파일들 선택 (최대 max_files개)
            files.sort(key=lambda x: x['last_modified'], reverse=True)
            recent_files = files[:max_files]
            
            # 여러 파일 로드 및 통합
            dataframes = []
            for file_info in recent_files:
                try:
                    # CSV 파일 다운로드
                    response = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=file_info['key']
                    )
                    
                    # CSV 데이터를 DataFrame으로 변환
                    csv_data = response['Body'].read().decode('utf-8')
                    df = pd.read_csv(io.StringIO(csv_data))
                    
                    # 파일 경로에서 날짜 정보 추출
                    path_parts = file_info['path_parts']
                    if len(path_parts) >= 4:
                        year = path_parts[2]
                        month = path_parts[3]
                        df['수집년월'] = f"{year}{month}"
                        df['파일경로'] = file_info['key']
                    
                    dataframes.append(df)
                    print(f"로드된 파일: {file_info['key']} ({len(df)}건)")
                    
                except Exception as e:
                    print(f"파일 로드 실패 {file_info['key']}: {e}")
                    continue
            
            if dataframes:
                # 모든 데이터프레임 합치기
                combined_df = pd.concat(dataframes, ignore_index=True)
                print(f"총 로드된 데이터: {len(combined_df)}건 (파일 {len(dataframes)}개)")
                return combined_df
            
            return None
            
        except ClientError as e:
            print(f"S3 데이터 로드 오류: {e}")
            return None
        except Exception as e:
            print(f"데이터 처리 오류: {e}")
            return None
    
    def load_data_by_year_month(self, data_type: str, lawd_cd: str, year: str, month: str) -> Optional[pd.DataFrame]:
        """특정 년월의 데이터를 로드"""
        if not self.s3_client:
            return None
        
        try:
            # 특정 년월의 파일들 조회
            prefix = f"data/{data_type}/{lawd_cd}/{year}/{month}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return None
            
            # CSV 파일들 필터링
            csv_files = []
            for obj in response['Contents']:
                if obj['Key'].endswith('.csv'):
                    csv_files.append({
                        'key': obj['Key'],
                        'last_modified': obj['LastModified']
                    })
            
            if not csv_files:
                return None
            
            # 파일들을 날짜순으로 정렬 (최신순)
            csv_files.sort(key=lambda x: x['last_modified'], reverse=True)
            
            # 모든 CSV 파일 로드 및 통합
            dataframes = []
            for file_info in csv_files:
                try:
                    # CSV 파일 다운로드
                    response = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=file_info['key']
                    )
                    
                    # CSV 데이터를 DataFrame으로 변환
                    csv_data = response['Body'].read().decode('utf-8')
                    df = pd.read_csv(io.StringIO(csv_data))
                    
                    # 파일 정보 추가
                    df['수집년월'] = f"{year}{month.zfill(2)}"
                    df['파일경로'] = file_info['key']
                    
                    dataframes.append(df)
                    print(f"로드된 파일: {file_info['key']} ({len(df)}건)")
                    
                except Exception as e:
                    print(f"파일 로드 실패 {file_info['key']}: {e}")
                    continue
            
            if dataframes:
                # 모든 데이터프레임 합치기
                combined_df = pd.concat(dataframes, ignore_index=True)
                print(f"총 로드된 데이터: {len(combined_df)}건 (파일 {len(dataframes)}개)")
                return combined_df
            
            return None
            
        except ClientError as e:
            print(f"S3 데이터 로드 오류: {e}")
            return None
        except Exception as e:
            print(f"데이터 처리 오류: {e}")
            return None

