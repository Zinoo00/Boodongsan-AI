"""
Real Estate Data Collector for Korean Government APIs
Collects data from MOLIT (Ministry of Land, Infrastructure and Transport) APIs
"""

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from ...core.config import settings

logger = logging.getLogger(__name__)


class RealEstateCollector:
    """Collector for Korean real estate data from government APIs"""
    
    def __init__(self):
        self.session = None
        self.service_key = settings.MOLIT_API_KEY
        self.base_urls = {
            "apartment_trade": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev",
            "apartment_rent": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent",
            "officetel_trade": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiTrade",
            "officetel_rent": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiRent",
            "villa_trade": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcRHTrade",
            "villa_rent": "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcRHRent",
        }
        
        # Seoul district codes (example - expand as needed)
        self.district_codes = {
            "강남구": "11680",
            "강동구": "11740",
            "강북구": "11305",
            "강서구": "11500",
            "관악구": "11620",
            "광진구": "11215",
            "구로구": "11530",
            "금천구": "11545",
            "노원구": "11350",
            "도봉구": "11320",
            "동대문구": "11230",
            "동작구": "11590",
            "마포구": "11440",
            "서대문구": "11410",
            "서초구": "11650",
            "성동구": "11200",
            "성북구": "11290",
            "송파구": "11710",
            "양천구": "11470",
            "영등포구": "11560",
            "용산구": "11170",
            "은평구": "11380",
            "종로구": "11110",
            "중구": "11140",
            "중랑구": "11260",
        }
        
        # Rate limiting
        self.request_delay = 1.0  # Delay between requests in seconds
        self.last_request_time = 0
    
    async def initialize(self):
        """Initialize HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def collect_all_data(
        self,
        year_month: str = None,
        districts: list[str] = None,
        property_types: list[str] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Collect all real estate data
        
        Args:
            year_month: YYYYMM format (defaults to current month)
            districts: List of district names (defaults to all Seoul districts)
            property_types: List of property types (defaults to all types)
        """
        await self.initialize()
        
        try:
            # Set defaults
            if not year_month:
                year_month = datetime.now().strftime("%Y%m")
            
            if not districts:
                districts = list(self.district_codes.keys())
            
            if not property_types:
                property_types = list(self.base_urls.keys())
            
            total_combinations = len(districts) * len(property_types)
            processed = 0
            
            logger.info(f"Starting data collection for {total_combinations} combinations")
            
            for district in districts:
                district_code = self.district_codes.get(district)
                if not district_code:
                    logger.warning(f"Unknown district: {district}")
                    continue
                
                for property_type in property_types:
                    try:
                        async for record in self.collect_district_data(
                            district=district,
                            district_code=district_code,
                            property_type=property_type,
                            year_month=year_month
                        ):
                            yield record
                        
                        processed += 1
                        logger.info(f"Completed {processed}/{total_combinations}: {district} - {property_type}")
                        
                    except Exception as e:
                        logger.error(f"Failed to collect data for {district} - {property_type}: {str(e)}")
                        continue
            
            logger.info(f"Data collection completed: {processed}/{total_combinations} successful")
            
        finally:
            await self.close()
    
    async def collect_district_data(
        self,
        district: str,
        district_code: str,
        property_type: str,
        year_month: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Collect data for specific district and property type
        
        Args:
            district: District name
            district_code: District code for API
            property_type: Property type key
            year_month: YYYYMM format
        """
        
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Build API URL
            url = self.base_urls[property_type]
            params = {
                "serviceKey": self.service_key,
                "pageNo": "1",
                "numOfRows": "1000",  # Maximum allowed
                "LAWD_CD": district_code,
                "DEAL_YMD": year_month
            }
            
            url_with_params = f"{url}?{urlencode(params)}"
            
            async with self.session.get(url_with_params) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse XML response
                    records = self._parse_xml_response(content, property_type, district)
                    
                    for record in records:
                        yield record
                        
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error collecting data for {district} - {property_type}: {str(e)}")
    
    async def _rate_limit(self):
        """Apply rate limiting to avoid API throttling"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _parse_xml_response(
        self,
        xml_content: str,
        property_type: str,
        district: str
    ) -> list[dict[str, Any]]:
        """Parse XML response from MOLIT API"""
        
        records = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Check for errors
            result_code = root.find(".//resultCode")
            if result_code is not None and result_code.text != "00":
                result_msg = root.find(".//resultMsg")
                error_msg = result_msg.text if result_msg is not None else "Unknown error"
                logger.error(f"API error: {error_msg}")
                return records
            
            # Find all items
            items = root.findall(".//item")
            
            for item in items:
                try:
                    record = self._parse_item(item, property_type, district)
                    if record:
                        records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse item: {str(e)}")
                    continue
            
            logger.info(f"Parsed {len(records)} records for {district} - {property_type}")
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing XML: {str(e)}")
        
        return records
    
    def _parse_item(
        self,
        item: ET.Element,
        property_type: str,
        district: str
    ) -> dict[str, Any] | None:
        """Parse individual item from XML"""
        
        try:
            # Common fields
            record = {
                "data_source": "MOLIT",
                "property_type": self._map_property_type(property_type),
                "transaction_type": self._map_transaction_type(property_type),
                "sido": "서울특별시",
                "sigungu": district,
                "collected_at": datetime.utcnow().isoformat(),
            }
            
            # Extract fields with safe parsing
            field_mapping = {
                "거래금액": ("price", self._parse_price),
                "보증금액": ("deposit", self._parse_price),
                "월세금액": ("monthly_rent", self._parse_price),
                "건축년도": ("building_year", self._parse_int),
                "년": ("transaction_year", self._parse_int),
                "월": ("transaction_month", self._parse_int),
                "일": ("transaction_day", self._parse_int),
                "전용면적": ("area_m2", self._parse_float),
                "층": ("floor", self._parse_int),
                "아파트": ("building_name", str),
                "연립다세대": ("building_name", str),
                "오피스텔": ("building_name", str),
                "법정동": ("dong", str),
                "지번": ("jibun", str),
            }
            
            for xml_field, (record_field, parser) in field_mapping.items():
                element = item.find(xml_field)
                if element is not None and element.text:
                    try:
                        record[record_field] = parser(element.text.strip())
                    except (ValueError, TypeError):
                        continue
            
            # Build transaction date
            if all(field in record for field in ["transaction_year", "transaction_month", "transaction_day"]):
                try:
                    transaction_date = datetime(
                        year=record["transaction_year"],
                        month=record["transaction_month"], 
                        day=record["transaction_day"]
                    )
                    record["transaction_date"] = transaction_date.isoformat()
                except ValueError:
                    pass
            
            # Build address
            address_parts = [record["sido"], record["sigungu"]]
            if "dong" in record:
                address_parts.append(record["dong"])
            if "jibun" in record:
                address_parts.append(record["jibun"])
            
            record["address"] = " ".join(address_parts)
            
            # Calculate area in pyeong
            if "area_m2" in record:
                record["area_pyeong"] = round(record["area_m2"] / 3.3058, 2)
            
            # Validate required fields
            required_fields = ["price", "area_m2", "building_year", "address"]
            if not all(field in record for field in required_fields):
                logger.warning(f"Missing required fields in record: {record}")
                return None
            
            # Generate unique source ID
            record["source_id"] = self._generate_source_id(record)
            
            return record
            
        except Exception as e:
            logger.error(f"Error parsing item: {str(e)}")
            return None
    
    def _map_property_type(self, api_property_type: str) -> str:
        """Map API property type to standard property type"""
        mapping = {
            "apartment_trade": "아파트",
            "apartment_rent": "아파트",
            "officetel_trade": "오피스텔",
            "officetel_rent": "오피스텔",
            "villa_trade": "빌라",
            "villa_rent": "빌라",
        }
        return mapping.get(api_property_type, "기타")
    
    def _map_transaction_type(self, api_property_type: str) -> str:
        """Map API property type to transaction type"""
        if "trade" in api_property_type:
            return "매매"
        elif "rent" in api_property_type:
            return "전세"  # API doesn't distinguish 전세/월세, need to check deposit
        else:
            return "기타"
    
    def _parse_price(self, value: str) -> int:
        """Parse price string to integer (in won)"""
        # Remove commas and convert to integer
        cleaned = value.replace(",", "").replace(" ", "")
        
        # Handle different units
        if "억" in cleaned or "만" in cleaned:
            # Korean number format
            eok_amount = 0
            man_amount = 0
            
            if "억" in cleaned:
                parts = cleaned.split("억")
                eok_amount = int(parts[0]) if parts[0] else 0
                remaining = parts[1] if len(parts) > 1 else ""
            else:
                remaining = cleaned
            
            if "만" in remaining:
                man_parts = remaining.split("만")
                man_amount = int(man_parts[0]) if man_parts[0] else 0
            
            # Convert to won (억 = 100,000,000, 만 = 10,000)
            return (eok_amount * 100000000) + (man_amount * 10000)
        
        else:
            # Direct number
            return int(cleaned)
    
    def _parse_int(self, value: str) -> int:
        """Parse integer value"""
        return int(value.replace(",", "").strip())
    
    def _parse_float(self, value: str) -> float:
        """Parse float value"""
        return float(value.replace(",", "").strip())
    
    def _generate_source_id(self, record: dict[str, Any]) -> str:
        """Generate unique source ID for record"""
        import hashlib
        
        # Create unique ID from key fields
        key_fields = [
            record.get("address", ""),
            str(record.get("price", 0)),
            str(record.get("area_m2", 0)),
            record.get("transaction_date", ""),
            record.get("property_type", ""),
            record.get("transaction_type", "")
        ]
        
        key_string = "|".join(key_fields)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def test_connection(self) -> bool:
        """Test API connection"""
        await self.initialize()
        
        try:
            # Test with a simple request
            test_district = "11680"  # 강남구
            test_year_month = datetime.now().strftime("%Y%m")
            
            url = self.base_urls["apartment_trade"]
            params = {
                "serviceKey": self.service_key,
                "pageNo": "1",
                "numOfRows": "1",
                "LAWD_CD": test_district,
                "DEAL_YMD": test_year_month
            }
            
            url_with_params = f"{url}?{urlencode(params)}"
            
            async with self.session.get(url_with_params) as response:
                if response.status == 200:
                    content = await response.text()
                    root = ET.fromstring(content)
                    
                    result_code = root.find(".//resultCode")
                    if result_code is not None and result_code.text == "00":
                        logger.info("MOLIT API connection test successful")
                        return True
                    else:
                        result_msg = root.find(".//resultMsg")
                        error_msg = result_msg.text if result_msg is not None else "Unknown error"
                        logger.error(f"MOLIT API test failed: {error_msg}")
                        return False
                else:
                    logger.error(f"MOLIT API test failed: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"MOLIT API connection test failed: {str(e)}")
            return False
        
        finally:
            await self.close()
    
    def get_available_districts(self) -> list[str]:
        """Get list of available districts"""
        return list(self.district_codes.keys())
    
    def get_available_property_types(self) -> list[str]:
        """Get list of available property types"""
        return list(self.base_urls.keys())