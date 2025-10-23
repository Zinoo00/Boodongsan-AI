"""
기본 데이터 수집기 클래스
모든 데이터 수집기가 상속받는 기본 클래스입니다.
"""

import os
import sys
import time
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 직접 config.py import
import importlib.util
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.py')
spec = importlib.util.spec_from_file_location("config", config_path)
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)
Config = config_module.Config


class BaseDataCollector:
    """기본 데이터 수집기 클래스"""

    def __init__(self):
        self.config = Config()
        self.session = requests.Session()

    def make_api_request(self, api_type: str, base_url: str, api_name: str, lawd_cd: str = None, deal_ymd: str = None) -> str:
        """
        공공데이터포털 API 호출

        Args:
            api_type: API 타입
            base_url: API 기본 URL
            api_name: API 이름
            lawd_cd: 법정동 코드 (기본값: 41480 - 파주시)
            deal_ymd: 거래 년월 (기본값: 202412)

        Returns:
            API 응답 데이터
        """
        lawd_cd = lawd_cd or '41480'  # 기본값
        deal_ymd = deal_ymd or '202412'  # 기본값

        params = {
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd,
            'serviceKey': self.config.SERVICE_KEY
        }

        for attempt in range(self.config.MAX_RETRIES):
            try:
                print(f"{api_name} API 요청 중... (시도 {attempt + 1}/{self.config.MAX_RETRIES})")
                print(f"URL: {base_url}")
                print(f"파라미터: LAWD_CD={lawd_cd}, DEAL_YMD={deal_ymd}")

                response = self.session.get(
                    base_url,
                    params=params,
                    timeout=self.config.TIMEOUT
                )

                print(f"응답 상태 코드: {response.status_code}")
                print(f"응답 내용 길이: {len(response.text)}")
                print(f"응답 내용 (처음 500자): {response.text[:500]}")

                response.raise_for_status()

                if "HTTP ROUTING ERROR" in response.text:
                    print("경고: HTTP ROUTING ERROR가 발생했습니다. API 키나 파라미터를 확인해주세요.")
                    return response.text

                return response.text

            except requests.exceptions.RequestException as e:
                print(f"API 요청 실패 (시도 {attempt + 1}): {e}")
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"API 요청이 {self.config.MAX_RETRIES}번 시도 후 실패했습니다.")

    def parse_response(self, response_text: str, api_type: str, api_name: str) -> List[Dict]:
        """
        API 응답 텍스트를 파싱하여 데이터 추출

        Args:
            response_text: API 응답 텍스트
            api_type: API 타입
            api_name: API 이름

        Returns:
            파싱된 데이터 리스트
        """
        print(f"{api_name} 데이터 파싱 중...")

        if "HTTP ROUTING ERROR" in response_text:
            print("❌ API 오류: HTTP ROUTING ERROR")
            print("API 키나 파라미터를 확인해주세요.")
            return []

        if response_text.strip().startswith('<?xml'):
            return self._parse_xml_response(response_text, api_type)

        lines = response_text.strip().split('\n')

        if not lines or lines[0] != '000OK':
            print("경고: 응답이 '000OK'로 시작하지 않습니다.")
            print(f"실제 응답 시작: {lines[0] if lines else '빈 응답'}")
            return []

        data_list = []

        for line in lines[1:]:
            if line.strip():
                try:
                    parsed_data = self._parse_line(line, api_type)
                    if parsed_data:
                        data_list.append(parsed_data)
                except Exception as e:
                    print(f"라인 파싱 실패: {line[:100]}... - {e}")
                    continue

        print(f"총 {len(data_list)}개의 데이터 항목을 파싱했습니다.")
        return data_list

    def _parse_xml_response(self, response_text: str, api_type: str) -> List[Dict]:
        """XML 응답 파싱 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다.")

    def _get_xml_text(self, element, tag_name: str) -> str:
        """XML 요소에서 텍스트 추출"""
        tag = element.find(tag_name)
        return tag.text.strip() if tag is not None and tag.text else ""

    def _parse_line(self, line: str, api_type: str) -> Optional[Dict]:
        """단일 라인을 파싱하여 구조화된 데이터로 변환 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다.")

    def collect_data(self, data_type: str, lawd_cd: str = None, deal_ymd: str = None) -> dict:
        """데이터 수집 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다.")

    def save_data(self, data_dict: dict, base_filename: str = None, data_type: str = None, deal_ymd: str = None, lawd_cd: str = None) -> dict:
        """
        정제된 데이터와 raw 데이터를 분리해서 저장
        새로운 폴더 구조: data/{lawd_cd}/{category}/{year}/{month}/

        Args:
            data_dict: collect_data에서 반환된 데이터 딕셔너리
            base_filename: 기본 파일명 (확장자 제외)
            data_type: 데이터 타입
            deal_ymd: 거래 년월 (YYYYMM 형식)
            lawd_cd: 법정동 코드

        Returns:
            저장된 파일 경로들을 포함한 딕셔너리
        """
        if base_filename is None:
            base_filename = f"{data_type}_data"

        # 법정동 코드 설정
        lawd_cd = lawd_cd or '41480'  # 기본값

        # 데이터 타입에 따른 카테고리 폴더 결정
        category_map = {
            'apt_rent': 'apartment',
            'apt_trade': 'apartment',
            'rh_rent': 'rh',
            'rh_trade': 'rh',
            'offi_rent': 'officetel',
            'offi_trade': 'officetel'
        }

        category = category_map.get(data_type, 'unknown')

        # 년도와 월 추출
        if deal_ymd and len(deal_ymd) == 6:
            year = deal_ymd[:4]
            month = deal_ymd[4:6]
        else:
            # 기본값 설정
            from datetime import datetime
            now = datetime.now()
            year = str(now.year)
            month = f"{now.month:02d}"

        # 폴더 경로 생성: data/{lawd_cd}/{category}/{year}/{month}/
        folder_path = os.path.join(self.config.DATA_DIR, lawd_cd, category, year, month)
        os.makedirs(folder_path, exist_ok=True)

        saved_files = {}

        if 'clean_data' in data_dict and data_dict['clean_data'] is not None:
            clean_filename = f"{base_filename}_clean.csv"
            clean_file_path = os.path.join(folder_path, clean_filename)
            data_dict['clean_data'].to_csv(clean_file_path, index=False, encoding='utf-8-sig')
            saved_files['clean_data'] = clean_file_path
            print(f"정제된 데이터 저장: {clean_file_path}")

        if 'raw_data' in data_dict and data_dict['raw_data'] is not None:
            raw_filename = f"{base_filename}_raw.csv"
            raw_file_path = os.path.join(folder_path, raw_filename)
            data_dict['raw_data'].to_csv(raw_file_path, index=False, encoding='utf-8-sig')
            saved_files['raw_data'] = raw_file_path
            print(f"Raw 데이터 저장: {raw_file_path}")

        if 'response_text' in data_dict and data_dict['response_text'].strip().startswith('<?xml'):
            xml_filename = f"{base_filename}_response.xml"
            xml_file_path = os.path.join(folder_path, xml_filename)
            with open(xml_file_path, 'w', encoding='utf-8') as f:
                f.write(data_dict['response_text'])
            saved_files['response_xml'] = xml_file_path
            print(f"응답 XML 저장: {xml_file_path}")

        return saved_files

    def display_summary(self, data_dict: dict, data_type: str, data_type_name: str):
        """
        수집된 데이터의 요약 정보 출력

        Args:
            data_dict: collect_data에서 반환된 데이터 딕셔너리
            data_type: 데이터 타입
            data_type_name: 데이터 타입 이름
        """
        print(f"\n=== {data_type_name} 데이터 요약 ===")

        if 'clean_data' in data_dict and data_dict['clean_data'] is not None:
            clean_df = data_dict['clean_data']
            print(f"정제된 데이터: {len(clean_df)}개 항목, {len(clean_df.columns)}개 컬럼")
            print(f"컬럼명: {list(clean_df.columns)}")

            if not clean_df.empty:
                print(f"\n=== {data_type_name} 정제된 데이터 샘플 ===")
                print(clean_df.head())

                print(f"\n=== {data_type_name} 정제된 데이터 기본 통계 ===")
                print(clean_df.describe())

        if 'raw_data' in data_dict and data_dict['raw_data'] is not None:
            raw_df = data_dict['raw_data']
            print(f"\nRaw 데이터: {len(raw_df)}개 항목, {len(raw_df.columns)}개 컬럼")
            print(f"Raw 데이터 컬럼명: {list(raw_df.columns)}")

            if not raw_df.empty:
                print(f"\n=== {data_type_name} Raw 데이터 샘플 ===")
                print(raw_df.head())

        if 'response_text' in data_dict:
            response_text = data_dict['response_text']
            print(f"\n응답 텍스트 길이: {len(response_text)}자")
            if response_text.strip().startswith('<?xml'):
                print("응답 형식: XML")
            else:
                print("응답 형식: 텍스트")
