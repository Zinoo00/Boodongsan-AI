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

    def make_api_request(self, api_type: str, base_url: str, api_name: str, lawd_cd: str, deal_ymd: str) -> str:
        """
        공공데이터포털 API 호출

        Args:
            api_type: API 타입
            base_url: API 기본 URL
            api_name: API 이름
            lawd_cd: 법정동 코드 (필수)
            deal_ymd: 거래 년월 (필수)

        Returns:
            API 응답 데이터
        """
        if not lawd_cd:
            raise ValueError("lawd_cd는 필수 파라미터입니다.")
        if not deal_ymd:
            raise ValueError("deal_ymd는 필수 파라미터입니다.")

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

        # 텍스트 파싱은 현재 사용하지 않음 (XML 파싱 사용)
        pass

        print(f"총 {len(data_list)}개의 데이터 항목을 파싱했습니다.")
        return data_list

    def _parse_xml_response(self, response_text: str, api_type: str) -> List[Dict]:
        """XML 응답 파싱 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다.")

    def _get_xml_text(self, element, tag_name: str) -> str:
        """XML 요소에서 텍스트 추출"""
        tag = element.find(tag_name)
        return tag.text.strip() if tag is not None and tag.text else ""


    def collect_data(self, data_type: str, lawd_cd: str, deal_ymd: str) -> dict:
        """데이터 수집 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다.")


