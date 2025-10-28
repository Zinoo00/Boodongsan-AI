"""
연립다세대 데이터 수집기
연립다세대 전월세 및 매매 실거래가 데이터를 수집합니다.
"""

import pandas as pd
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from .base_collector import BaseDataCollector


class RHDataCollector(BaseDataCollector):
    """연립다세대 데이터 수집기 (전월세 + 매매)"""

    def make_api_request(self, api_type: str = "rh_rent", lawd_cd: str = None, deal_ymd: str = None) -> str:
        """
        공공데이터포털 API 호출

        Args:
            api_type: API 타입 ("rh_rent", "rh_trade")
            lawd_cd: 법정동 코드 (기본값: 41480 - 파주시)
            deal_ymd: 거래 년월 (기본값: 202412)

        Returns:
            API 응답 데이터
        """
        # API 타입에 따른 URL 선택
        if api_type == "rh_rent":
            base_url = self.config.RH_RENT_BASE_URL
            api_name = "연립다세대 전월세"
        elif api_type == "rh_trade":
            base_url = self.config.RH_TRADE_BASE_URL
            api_name = "연립다세대 매매 실거래가"
        else:
            raise ValueError("api_type은 'rh_rent' 또는 'rh_trade'여야 합니다.")

        return super().make_api_request(api_type, base_url, api_name, lawd_cd, deal_ymd)

    def parse_response(self, response_text: str, api_type: str = "rh_rent") -> List[Dict]:
        """
        API 응답 텍스트를 파싱하여 데이터 추출

        Args:
            response_text: API 응답 텍스트
            api_type: API 타입 ("rh_rent", "rh_trade")

        Returns:
            파싱된 데이터 리스트
        """
        api_type_names = {
            "rh_rent": "연립다세대 전월세",
            "rh_trade": "연립다세대 매매"
        }
        api_name = api_type_names.get(api_type, "")
        return super().parse_response(response_text, api_type, api_name)

    def _parse_xml_response(self, response_text: str, api_type: str = "rh_rent") -> List[Dict]:
        """XML 응답 파싱"""
        try:
            root = ET.fromstring(response_text)

            result_code = root.find('.//resultCode')
            if result_code is not None and result_code.text != '000':
                raise Exception(f"API 오류: {result_code.text}")

            items = root.findall('.//item')
            if not items:
                print("경고: XML 응답에 데이터가 없습니다.")
                return []

            data_list = []
            raw_data_list = []

            for item in items:
                try:
                    if api_type == "rh_rent":
                        # 연립다세대 전월세 데이터 파싱
                        parsed_data = {
                            'house_name': self._get_xml_text(item, 'mhouseNm'),
                            'house_type': self._get_xml_text(item, 'houseType'),
                            'build_year': self._get_xml_text(item, 'buildYear'),
                            'deal_year': self._get_xml_text(item, 'dealYear'),
                            'deal_month': self._get_xml_text(item, 'dealMonth'),
                            'deal_day': self._get_xml_text(item, 'dealDay'),
                            'deposit': self._get_xml_text(item, 'deposit'),
                            'monthly_rent': self._get_xml_text(item, 'monthlyRent'),
                            'area': self._get_xml_text(item, 'excluUseAr'),
                            'floor': self._get_xml_text(item, 'floor'),
                            'lawd_code': self._get_xml_text(item, 'sggCd'),
                            'dong': self._get_xml_text(item, 'umdNm'),
                            'jibun': self._get_xml_text(item, 'jibun'),
                            'contract_type': self._get_xml_text(item, 'contractType'),
                            'contract_term': self._get_xml_text(item, 'contractTerm'),
                            'pre_deposit': self._get_xml_text(item, 'preDeposit'),
                            'pre_monthly_rent': self._get_xml_text(item, 'preMonthlyRent'),
                            'use_rr_right': self._get_xml_text(item, 'useRRRight')
                        }
                    else:  # rh_trade
                        # 연립다세대 매매 데이터 파싱
                        parsed_data = {
                            'house_name': self._get_xml_text(item, 'mhouseNm'),
                            'house_type': self._get_xml_text(item, 'houseType'),
                            'build_year': self._get_xml_text(item, 'buildYear'),
                            'deal_year': self._get_xml_text(item, 'dealYear'),
                            'deal_month': self._get_xml_text(item, 'dealMonth'),
                            'deal_day': self._get_xml_text(item, 'dealDay'),
                            'deal_amount': self._get_xml_text(item, 'dealAmount'),
                            'area': self._get_xml_text(item, 'excluUseAr'),
                            'land_area': self._get_xml_text(item, 'landAr'),
                            'floor': self._get_xml_text(item, 'floor'),
                            'lawd_code': self._get_xml_text(item, 'sggCd'),
                            'dong': self._get_xml_text(item, 'umdNm'),
                            'jibun': self._get_xml_text(item, 'jibun'),
                            'buyer_type': self._get_xml_text(item, 'buyerGbn'),
                            'seller_type': self._get_xml_text(item, 'slerGbn'),
                            'dealing_type': self._get_xml_text(item, 'dealingGbn'),
                            'estate_agent': self._get_xml_text(item, 'estateAgentSggNm'),
                            'rgst_date': self._get_xml_text(item, 'rgstDate')
                        }

                    data_list.append(parsed_data)

                    raw_data = {
                        'raw_xml': ET.tostring(item, encoding='unicode'),
                        'house_name': self._get_xml_text(item, 'mhouseNm'),
                        'deal_date': f"{self._get_xml_text(item, 'dealYear')}-{self._get_xml_text(item, 'dealMonth')}-{self._get_xml_text(item, 'dealDay')}"
                    }
                    raw_data_list.append(raw_data)

                except Exception as e:
                    print(f"XML 아이템 파싱 실패: {e}")
                    continue

            print(f"XML 파싱 완료: {len(data_list)}개 항목")

            return {
                'clean_data': data_list,
                'raw_data': raw_data_list
            }

        except ET.ParseError as e:
            raise Exception(f"XML 파싱 오류: {e}")
        except Exception as e:
            raise Exception(f"XML 응답 처리 오류: {e}")


    def collect_rh_rent_data(self, lawd_cd: str, deal_ymd: str) -> dict:
        """
        연립다세대 전월세 데이터 수집 및 DataFrame 반환

        Args:
            lawd_cd: 법정동 코드
            deal_ymd: 거래 년월

        Returns:
            정제된 데이터와 raw 데이터를 포함한 딕셔너리
        """
        print("연립다세대 전월세 데이터 수집을 시작합니다...")

        response_text = self.make_api_request("rh_rent", lawd_cd, deal_ymd)
        parsed_data = self.parse_response(response_text, "rh_rent")

        if isinstance(parsed_data, dict) and 'clean_data' in parsed_data:
            clean_df = pd.DataFrame(parsed_data['clean_data'])
            raw_df = pd.DataFrame(parsed_data['raw_data'])

            print(f"연립다세대 전월세 데이터 수집 완료: {len(clean_df)}개 항목 (정제된 데이터)")
            print(f"Raw 데이터: {len(raw_df)}개 항목")

            return {
                'clean_data': clean_df,
                'raw_data': raw_df,
                'response_text': response_text
            }
        else:
            df = pd.DataFrame(parsed_data)
            print(f"연립다세대 전월세 데이터 수집 완료: {len(df)}개 항목")
            return {
                'clean_data': df,
                'raw_data': None,
                'response_text': response_text
            }

    def collect_rh_trade_data(self, lawd_cd: str, deal_ymd: str) -> dict:
        """
        연립다세대 매매 실거래가 데이터 수집 및 DataFrame 반환

        Args:
            lawd_cd: 법정동 코드
            deal_ymd: 거래 년월

        Returns:
            정제된 데이터와 raw 데이터를 포함한 딕셔너리
        """
        print("연립다세대 매매 실거래가 데이터 수집을 시작합니다...")

        response_text = self.make_api_request("rh_trade", lawd_cd, deal_ymd)
        parsed_data = self.parse_response(response_text, "rh_trade")

        if isinstance(parsed_data, dict) and 'clean_data' in parsed_data:
            clean_df = pd.DataFrame(parsed_data['clean_data'])
            raw_df = pd.DataFrame(parsed_data['raw_data'])

            print(f"연립다세대 매매 데이터 수집 완료: {len(clean_df)}개 항목 (정제된 데이터)")
            print(f"Raw 데이터: {len(raw_df)}개 항목")

            return {
                'clean_data': clean_df,
                'raw_data': raw_df,
                'response_text': response_text
            }
        else:
            df = pd.DataFrame(parsed_data)
            print(f"연립다세대 매매 데이터 수집 완료: {len(df)}개 항목")
            return {
                'clean_data': df,
                'raw_data': None,
                'response_text': response_text
            }


