"""
국토교통부 보도자료(분야=주택토지) 첨부 PDF 수집기
- 목록: https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp
- 상세: 제목 클릭(dtl.jsp)
- 상세에서 첨부 PDF 링크 추출하여 S3(bds-collect/data/policy_document) 업로드

실행 예시:
    python -m src.collectors.molit_policy_collector --max 3
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import boto3
import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


BASE_URL = "https://www.molit.go.kr/USR/NEWS/m_71/"
LIST_URL = urljoin(BASE_URL, "lst.jsp")

# 고정 정책(주거안정) 페이지 URL 상수
STABLE_POLICY_URLS: List[str] = [
    "https://www.molit.go.kr/policy/stable/sta_a_01.jsp",
    "https://www.molit.go.kr/policy/stable/sta_a_02.jsp",
    "https://www.molit.go.kr/policy/stable/sta_a_03.jsp",
    "https://www.molit.go.kr/policy/stable/sta_b_01.jsp",
    "https://www.molit.go.kr/policy/stable/sta_b_02.jsp",
    "https://www.molit.go.kr/policy/stable/sta_b_03.jsp",
    "https://www.molit.go.kr/policy/stable/sta_d_01.jsp",
]


class MolitPolicyCollector:
    def __init__(
        self,
        s3_bucket: str = "bds-collect",
        s3_prefix: str = "data/policy_document",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) PythonRequests/2.x",
        })
        self.s3 = boto3.client("s3")

    def collect(self, max_items: int = 3, start_date: str = None, end_date: str = None) -> List[Dict[str, str]]:
        rows = self._fetch_list()
        # 분야가 '주택토지' 인 항목만 필터
        housing_rows = [r for r in rows if r.get("sector") == "주택토지"]
        
        # 날짜 필터링
        if start_date or end_date:
            housing_rows = self._filter_by_date(housing_rows, start_date, end_date)
        
        targets = housing_rows[:max_items]

        results: List[Dict[str, str]] = []
        for idx, item in enumerate(targets, 1):
            try:
                logger.info(f"[{idx}/{len(targets)}] {item['title']} ({item['date']})")
                detail_url = urljoin(BASE_URL, item["href"])  # e.g., dtl.jsp?lcmspage=1&id=...
                pdf_url, filename = self._extract_pdf(detail_url)
                if not pdf_url:
                    logger.warning("PDF 링크를 찾지 못했습니다.")
                    continue

                s3_key = self._download_and_upload(pdf_url, filename, item)
                if s3_key:
                    results.append({
                        "title": item["title"],
                        "date": item["date"],
                        "detail_url": detail_url,
                        "pdf_url": pdf_url,
                        "s3_url": f"s3://{self.s3_bucket}/{s3_key}",
                    })
                    logger.info(f"✅ 업로드 완료: s3://{self.s3_bucket}/{s3_key}")
            except Exception as e:
                logger.error(f"항목 처리 실패: {e}")

        return results

    def collect_policy_pages_to_markdown(self, urls: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        고정 정책 페이지(예: https://www.molit.go.kr/policy/stable/sta_a_01.jsp 등)를 크롤링하여
        Markdown(.md)으로 변환 후 s3://{bucket}/data/policy_document/ 에 업로드한다.

        Returns: 업로드 결과 리스트 [{title, url, s3_url, key}]
        """
        results: List[Dict[str, str]] = []
        if not urls:
            urls = STABLE_POLICY_URLS

        for idx, url in enumerate(urls, 1):
            try:
                r = self.session.get(url, timeout=60)
                r.raise_for_status()
                soup = BeautifulSoup(r.content, "html.parser")

                title = self._extract_title(soup) or "무제"
                main_el = self._extract_main_content_element(soup)
                md_body = self._html_to_markdown(main_el)

                # 최종 Markdown 문서 구성
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                md_text = f"# {title}\n\n" \
                          f"원문: {url}\n\n" \
                          f"수집시각: {created_at}\n\n" \
                          f"---\n\n" \
                          f"{md_body}\n"

                # 파일명/키 생성 (중복 방지: URL 슬러그 + 짧은 해시 포함)
                date_compact = datetime.now().strftime("%Y%m%d")
                safe_title = self._sanitize_filename(title)
                slug = self._sanitize_filename(self._slug_from_url(url) or "page")
                filename = f"{date_compact}_{slug}_{safe_title}.md"
                s3_key = f"{self.s3_prefix}/{filename}"

                self.s3.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=md_text.encode("utf-8"),
                    ContentType="text/markdown; charset=utf-8",
                    Metadata={
                        "title": self._ascii_only(title),
                        "source": self._ascii_only(url),
                        "download_time": datetime.now().isoformat(),
                    },
                )

                results.append({
                    "title": title,
                    "url": url,
                    "s3_url": f"s3://{self.s3_bucket}/{s3_key}",
                    "key": s3_key,
                })
                logger.info(f"✅ MD 업로드 완료: s3://{self.s3_bucket}/{s3_key}")

            except Exception as e:
                logger.error(f"정책 페이지 처리 실패({url}): {e}")

        return results

    def _fetch_list(self) -> List[Dict[str, str]]:
        """보도자료 목록 페이지에서 행 추출"""
        r = self.session.get(LIST_URL, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.select_one("table.bd_tbl")
        if not table:
            return []
        rows = []
        for tr in table.select("tbody tr"):
            tds = tr.select("td")
            if len(tds) < 4:
                continue
            title_a = tds[1].select_one("a")
            sector = tds[2].get_text(strip=True)
            date = tds[3].get_text(strip=True)
            if not title_a:
                continue
            rows.append({
                "title": title_a.get_text(strip=True),
                "href": title_a.get("href"),
                "sector": sector,
                "date": date,
            })
        return rows

    def _filter_by_date(self, rows: List[Dict[str, str]], start_date: str = None, end_date: str = None) -> List[Dict[str, str]]:
        """날짜 범위로 필터링 (YYYY-MM-DD 형식)"""
        from datetime import datetime
        
        filtered_rows = []
        
        for row in rows:
            date_str = row.get("date", "")
            if not date_str:
                continue
                
            try:
                # 날짜 파싱 (YYYY-MM-DD 형식)
                row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # 시작일 체크
                if start_date:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                    if row_date < start_dt:
                        continue
                
                # 종료일 체크
                if end_date:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                    if row_date > end_dt:
                        continue
                
                filtered_rows.append(row)
                
            except ValueError as e:
                logger.warning(f"날짜 파싱 실패: {date_str} - {e}")
                continue
        
        logger.info(f"날짜 필터링 결과: {len(filtered_rows)}건 (시작일: {start_date}, 종료일: {end_date})")
        return filtered_rows

    def _extract_pdf(self, detail_url: str) -> (Optional[str], Optional[str]):
        """상세 페이지에서 PDF 링크와 파일명 추출"""
        r = self.session.get(detail_url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        # 1) href에 .pdf 포함된 링크 우선 사용
        for a in soup.select("a"):
            href = a.get("href")
            if href and ".pdf" in href.lower():
                pdf_url = urljoin("https://www.molit.go.kr", href)
                filename = a.get_text(strip=True) or pdf_url.split("/")[-1]
                return pdf_url, filename

        # 2) 다음 후보: LCMS/Download 등 다운로드 엔드포인트
        for a in soup.select("a"):
            href = a.get("href")
            if href and ("/LCMS/" in href or "download" in href.lower()):
                pdf_url = urljoin("https://www.molit.go.kr", href)
                filename = a.get_text(strip=True) or pdf_url.split("/")[-1]
                return pdf_url, filename

        return None, None

    def _download_and_upload(
        self,
        pdf_url: str,
        filename: str,
        meta: Dict[str, str],
    ) -> Optional[str]:
        r = self.session.get(pdf_url, timeout=60, allow_redirects=True)
        r.raise_for_status()

        # S3 키: 접두사 제거한 정제 파일명만 사용 (동일 키면 overwrite 허용)
        safe_name = self._sanitize_filename(filename)
        # 확장자 보존
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"
        name, ext = (safe_name.rsplit('.', 1) + [""])[:2]
        ext = f".{ext}" if ext else ""
        cleaned_name = self._strip_leading_prefixes(name) + ext
        s3_key = f"{self.s3_prefix}/{cleaned_name}"

        # 메타데이터 ASCII 제한 처리
        def ascii_only(s: str) -> str:
            try:
                return (s or "").encode("utf-8").decode("ascii", "ignore")
            except Exception:
                return ""

        # 업로드 재시도
        last_err: Optional[Exception] = None
        for _ in range(3):
            try:
                self.s3.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=r.content,
                    ContentType="application/pdf",
                    Metadata={
                        "title": ascii_only(meta.get("title", "")),
                        "date": ascii_only(meta.get("date", "")),
                        "source": ascii_only(meta.get("href", "")),
                        "download_time": datetime.now().isoformat(),
                    },
                )
                return s3_key
            except Exception as e:
                last_err = e
        if last_err:
            logger.error(f"S3 업로드 실패: {last_err}")
        return None

    @staticmethod
    def _strip_leading_prefixes(name_without_ext: str) -> str:
        """
        파일명 앞의 날짜/조간 형태 접두사 제거.
        제거 패턴 예:
        - YYYYMMDD_
        - YYMMDD조간_
        - YYMMDD석간_
        - 다중 결합 예: YYYYMMDD_YYMMDD조간_
        """
        import re
        s = name_without_ext
        # 반복적으로 매칭 제거
        patterns = [
            r"^\d{8}_",              # 20251030_
            r"^\d{6}(조간|석간)_",   # 251031조간_ 또는 251031석간_
        ]
        changed = True
        while changed:
            changed = False
            for pat in patterns:
                new_s = re.sub(pat, "", s)
                if new_s != s:
                    s = new_s
                    changed = True
        return s.strip(" _-")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        import re
        base = name.strip().replace("\n", " ")
        base = re.sub(r"[^\w\s.-가-힣]", "", base)
        base = re.sub(r"\s+", "_", base)
        return base[:80]

    @staticmethod
    def _ascii_only(s: str) -> str:
        try:
            return (s or "").encode("utf-8").decode("ascii", "ignore")
        except Exception:
            return ""

    @staticmethod
    def _slug_from_url(url: str) -> str:
        try:
            path = urlparse(url).path.rstrip("/")
            if not path:
                return "page"
            last = path.split("/")[-1]
            # 확장자 제거
            if "." in last:
                last = last.split(".")[0]
            return last or "page"
        except Exception:
            return "page"

    @staticmethod
    def _short_hash(text: str, length: int = 8) -> str:
        # deprecated: 해시 미사용
        return ""

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> Optional[str]:
        # 우선순위: <h1> > <title>
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        if soup.title and soup.title.get_text(strip=True):
            return soup.title.get_text(strip=True)
        return None

    @staticmethod
    def _extract_main_content_element(soup: BeautifulSoup):
        # 사이트 공통 패턴 추정: main, #content, .content, .cont, .container 순으로 시도
        for sel in ["main", "#content", ".content", ".cont", ".container", "body"]:
            el = soup.select_one(sel)
            if el:
                return el
        return soup

    @staticmethod
    def _html_to_markdown(root) -> str:
        """간단한 HTML -> Markdown 변환기 (외부 의존성 없이 최소 구현)"""
        lines: List[str] = []

        def walk(el, depth=0):
            name = getattr(el, "name", None)
            if name is None:
                text = str(el).strip()
                if text:
                    lines.append(text)
                return

            # 헤딩 처리
            if name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                level = int(name[1])
                text = el.get_text(" ", strip=True)
                lines.append("#" * level + f" {text}")
                lines.append("")
                return

            # 리스트 처리
            if name in ["ul", "ol"]:
                for li in el.find_all("li", recursive=False):
                    prefix = "- " if name == "ul" else "1. "
                    lines.append(prefix + li.get_text(" ", strip=True))
                lines.append("")
                return

            # 단락 처리
            if name == "p":
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(text)
                    lines.append("")
                return

            # 표는 간단 텍스트로 전개
            if name == "table":
                for tr in el.find_all("tr"):
                    cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
                    if cells:
                        lines.append(" | ".join(cells))
                lines.append("")
                return

            # 그 외는 하위 탐색
            for child in el.children:
                walk(child, depth + 1)

        walk(root)
        # 공백 라인 정리
        compact: List[str] = []
        prev_blank = False
        for ln in lines:
            is_blank = (ln.strip() == "")
            if is_blank and prev_blank:
                continue
            compact.append(ln)
            prev_blank = is_blank
        return "\n".join(compact).strip() + "\n"


def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="MOLIT 수집기 (보도자료 PDF/정책 페이지 Markdown)")
    sub = parser.add_subparsers(dest="mode", required=True)

    # PDF 수집 모드
    pdf_p = sub.add_parser("news-pdf", help="보도자료(주택토지) PDF 수집")
    pdf_p.add_argument("--max", type=int, default=3, help="최대 수집 건수")
    pdf_p.add_argument("--start-date", type=str, help="시작일 (YYYY-MM-DD 형식)")
    pdf_p.add_argument("--end-date", type=str, help="종료일 (YYYY-MM-DD 형식)")

    # 정책 페이지 Markdown 수집 모드
    md_p = sub.add_parser("policy-md", help="정책 안정 페이지 Markdown 수집 (고정 URL 상수 사용)")
    args = parser.parse_args()

    collector = MolitPolicyCollector()
    if args.mode == "policy-md":
        results = collector.collect_policy_pages_to_markdown()
        print(f"총 {len(results)}건 업로드")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']} -> {r['s3_url']}")
    elif args.mode == "news-pdf":
        results = collector.collect(max_items=args.max, start_date=args.start_date, end_date=args.end_date)
        print(f"총 {len(results)}건 업로드")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']} ({r['date']}) -> {r['s3_url']}")


if __name__ == "__main__":
    main()


