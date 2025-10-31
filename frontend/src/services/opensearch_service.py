"""
OpenSearch 조회 유틸리티 (프론트엔드 전용 - 읽기 전용)
"""

import os
import logging
from typing import List
from urllib.parse import urlparse

from opensearchpy import OpenSearch


logger = logging.getLogger(__name__)


def _create_client() -> OpenSearch:
    endpoint = os.getenv("OPENSEARCH_ENDPOINT")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")

    if not endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT 환경변수가 설정되지 않았습니다.")

    parsed = urlparse(endpoint)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or endpoint
    port = parsed.port or (443 if scheme == "https" else 9200)

    client = OpenSearch(
        hosts=[{"host": host, "port": port, "scheme": scheme}],
        http_auth=(username, password) if username and password else None,
        use_ssl=(scheme == "https"),
        verify_certs=False,
        timeout=30,
    )
    return client


def get_level2_regions(index_name: str | None = None, max_terms: int = 1000) -> List[tuple[str, str]]:
    """lawd_codes 인덱스에서 level_2가 NULL이 아닌 지역 목록 조회

    반환 형식: List[(lawd_code, label)] where label = "level_1 level_2 level_3"
    """
    index = index_name or os.getenv("OPENSEARCH_INDEX_LAWD_CODES", "lawd_codes")
    client = _create_client()

    # 집계 대신 scroll 검색으로 고유 level_2 수집
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"exists": {"field": "level_2"}}
                ]
            }
        },
        "_source": ["level_1", "level_2", "level_3", "lawd_cd", "lawd_code"]
    }

    try:
        size = 1000
        res = client.search(index=index, body=query, size=size, scroll="1m")
        scroll_id = res.get("_scroll_id")
        hits = res.get("hits", {}).get("hits", [])

        unique = set()
        def collect(items):
            for h in items:
                src = h.get("_source", {})
                lvl2 = src.get("level_2")
                lvl1 = src.get("level_1")
                lvl3 = src.get("level_3")
                code = src.get("lawd_cd") or src.get("lawd_code")
                if lvl2 and code:
                    # level_1, level_2, level_3를 모두 포함하여 라벨 생성
                    name_parts = [part for part in [lvl1, lvl2, lvl3] if part]
                    label = " ".join(name_parts).strip()
                    unique.add((str(code), label))

        collect(hits)

        while hits and len(unique) < max_terms and scroll_id:
            res = client.scroll(scroll_id=scroll_id, scroll="1m")
            scroll_id = res.get("_scroll_id")
            hits = res.get("hits", {}).get("hits", [])
            collect(hits)

        # scroll 정리
        if scroll_id:
            try:
                client.clear_scroll(scroll_id=scroll_id)
            except Exception:
                pass

        regions = sorted(list(unique), key=lambda x: x[1])[:max_terms]
        return regions
    except Exception as e:
        logger.error(f"OpenSearch level_2 지역 조회 실패: {e}")
        return []


