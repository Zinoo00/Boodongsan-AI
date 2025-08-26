import requests
import xml.etree.ElementTree as ET
import pandas as pd

SERVICE_KEY = (
    "G9We7yRwh61X60sz4PLBz1T9AiTk8tJ14fdl2W53rRbtMK2yKG8FZLy6MrJ4jUXvR3baF0pmFXv5NxeUHwUACA=="
)
# 2. API 기본 정보
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent"
ENDPOINT = "/getRTMSDataSvcAptRent"

# 3. 요청 파라미터
params = {
    "serviceKey": SERVICE_KEY,
    "LAWD_CD": "11680",  # 강남구 코드
    "DEAL_YMD": "202401",  # 2024년 1월
    "numOfRows": "10",  # 일단 10개만 가져오기
}

print("🔍 API 호출 중...")
print(f"URL: {BASE_URL + ENDPOINT}")
print(f"지역: 강남구 (11680)")
print(f"기간: 2024년 1월")
print("-" * 50)

# 4. API 호출
try:
    response = requests.get(BASE_URL + ENDPOINT, params=params)
    print(f"✅ HTTP 상태코드: {response.status_code}")

    if response.status_code == 200:
        print("✅ API 호출 성공!")

        # XML 내용 일부 출력
        print("\n📄 응답 내용 (처음 500자):")
        print(response.text[:500])
        print("...")

        # XML 파싱 시도
        try:
            root = ET.fromstring(response.content)

            # 결과 코드 확인
            result_code = root.find(".//resultCode")
            result_msg = root.find(".//resultMsg")

            if result_code is not None:
                print(f"\n🔍 결과 코드: {result_code.text}")
                print(f"🔍 결과 메시지: {result_msg.text if result_msg is not None else 'N/A'}")

            # 데이터 항목 개수 확인
            items = root.findall(".//item")
            print(f"\n📊 조회된 데이터 개수: {len(items)}개")

            # 첫 번째 데이터 항목 출력
            if items:
                print("\n🏠 첫 번째 데이터 항목:")
                for child in items[0]:
                    print(f"  - {child.tag}: {child.text}")

        except ET.ParseError as e:
            print(f"❌ XML 파싱 오류: {e}")

    else:
        print(f"❌ API 호출 실패: {response.status_code}")
        print(f"응답 내용: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"❌ 네트워크 오류: {e}")

print("\n" + "=" * 50)
print("🎯 다음 단계:")
print("1. 위 결과가 정상이면 더 많은 데이터를 요청할 수 있습니다")
print("2. 다른 지역이나 다른 월 데이터도 조회 가능합니다")
print("3. CSV 파일로 저장하여 분석할 수 있습니다")
