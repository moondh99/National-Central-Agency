import os
import time
import re
import csv
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# 기본 설정
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE_RSS_URL = "https://www.hani.co.kr/rss/"


def _results_dir() -> str:
    """현재 파일 기준 결과 저장 디렉토리 경로를 반환합니다."""
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "results")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def fetch_rss_items(category: str = "all", max_items: int = 20) -> List[ET.Element]:
    """RSS 피드에서 item 요소들을 가져옵니다."""
    url = BASE_RSS_URL if category == "all" else f"{BASE_RSS_URL}{category}.xml"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    items = root.findall(".//item")
    return items[:max_items]


def _extract_text_from_soup(soup: BeautifulSoup) -> str:
    """기사 본문 텍스트를 soup에서 추출합니다."""
    selectors = [
        "div.article-text p",
        "div.article-body p",
        "div.article-text",
        "div#article-text",
        "div#contents p",
    ]
    texts: List[str] = []
    for sel in selectors:
        nodes = soup.select(sel)
        if nodes:
            # p 목록인 경우
            if all(hasattr(n, "get_text") for n in nodes):
                texts = [n.get_text(strip=True) for n in nodes]
            else:
                texts = [nodes[0].get_text(strip=True)]
            break

    content = "\n".join(t for t in texts if t)

    # 폴백: og:description
    if not content:
        og = soup.select_one('meta[property="og:description"]')
        if og and og.get("content"):
            content = og["content"].strip()

    # 공백 정리
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return content


def extract_reporter_name(soup: BeautifulSoup) -> str:
    """기사 페이지에서 기자명을 추출합니다."""
    candidates = [
        ".byline .name",
        ".byline",
        ".author",
        "p.byline",
        "span.name",
    ]
    for sel in candidates:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            # 이메일/직책 제거
            text = re.sub(r"\b[\w.]+@[\w.-]+\b", "", text)
            text = re.sub(r"\s{2,}", " ", text)
            text = text.replace("기자", "기자").strip()
            if text:
                return text
    return ""


def _parse_pubdate(pubdate: str) -> str:
    """RSS pubDate를 표준 문자열(YYYY-mm-dd HH:MM:SS)로 변환합니다."""
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(pubdate, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    # 실패 시 현재 시각
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_items(items: List[ET.Element], request_interval: float = 1.0) -> List[Dict[str, str]]:
    """RSS item 리스트를 순회하며 기사 데이터를 추출합니다."""
    articles: List[Dict[str, str]] = []
    for item in items:
        try:
            title = re.sub(r"<[^>]+>", "", item.findtext("title", "")).strip()
            link = item.findtext("link", "").strip()
            pubdate = item.findtext("pubDate", "")
            date_text = _parse_pubdate(pubdate) if pubdate else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # category: 일반 태그와 DC 네임스페이스 둘 다 시도
            category = ""
            cat_el = item.find("category")
            if cat_el is not None and cat_el.text:
                category = cat_el.text.strip()
            else:
                dc_cat = item.find("{http://purl.org/dc/elements/1.1/}category")
                if dc_cat is not None and dc_cat.text:
                    category = dc_cat.text.strip()

            # 기사 페이지 요청 1회로 soup 생성 후 본문/기자 추출
            resp = requests.get(link, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            content = _extract_text_from_soup(soup)
            reporter = "한겨레신문"

            # 본문이 매우 짧으면 RSS 설명 보강
            if len(content) < 200:
                desc_raw = item.findtext("description", "") or ""
                desc_raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", desc_raw, flags=re.S)
                desc_text = re.sub(r"<[^>]+>", "", desc_raw).strip()
                if desc_text:
                    content = desc_text + ("\n\n" + content if content else "")

            if content.strip():
                articles.append(
                    {
                        "언론사": "한겨레신문",
                        "제목": title,
                        "날짜": date_text,
                        "카테고리": category,
                        "기자명": reporter,
                        "본문": content,
                    }
                )
            # 서버 부하 방지
            time.sleep(request_interval)

        except Exception as e:
            # 실패 시 최소 정보로 보존
            desc_raw = item.findtext("description", "") or ""
            desc_raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", desc_raw, flags=re.S)
            desc_text = re.sub(r"<[^>]+>", "", desc_raw).strip()
            articles.append(
                {
                    "언론사": "한겨레신문",
                    "제목": re.sub(r"<[^>]+>", "", item.findtext("title", "")).strip(),
                    "날짜": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "카테고리": "",
                    "기자명": "한겨레신문",
                    "본문": desc_text,
                }
            )
            continue

    return articles


def save_articles(articles: List[Dict[str, str]], category: str = "all") -> Optional[str]:
    """기사 리스트를 CSV로 저장하고 파일 경로를 반환합니다."""
    if not articles:
        return None
    out_dir = _results_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cat_label = "전체" if category in (None, "", "all") else category
    filename = os.path.join(out_dir, f"한겨레신문_{cat_label}_{ts}.csv")
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["언론사", "제목", "날짜", "카테고리", "기자명", "본문"])
        writer.writeheader()
        writer.writerows(articles)
    return filename


def scrape_hani_category(category: str = "all", max_items: int = 20) -> Optional[str]:
    """단일 카테고리를 수집하여 CSV로 저장합니다."""
    items = fetch_rss_items(category=category, max_items=max_items)
    articles = parse_items(items)
    return save_articles(articles, category=category)


def scrape_hani_multiple_categories(categories: List[str], max_items: int = 20) -> List[str]:
    """여러 카테고리를 순회 수집합니다. 각 카테고리별 CSV를 저장하고 경로 목록 반환."""
    saved: List[str] = []
    for cat in categories:
        try:
            path = scrape_hani_category(cat, max_items=max_items)
            if path:
                saved.append(path)
        except Exception:
            continue
    return saved


def main():
    import argparse

    parser = argparse.ArgumentParser(description="한겨레신문 RSS 크롤러")
    parser.add_argument("-c", "--category", default="all", help="카테고리 (기본: all)")
    parser.add_argument("--categories", help="쉼표(,)로 구분된 다중 카테고리")
    parser.add_argument("-n", "--number", type=int, default=20, help="수집할 최대 기사 수")
    args = parser.parse_args()

    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        saved = scrape_hani_multiple_categories(cats, max_items=args.number)
        if saved:
            print(f"완료: {len(saved)}개 파일 저장")
            for p in saved:
                print(f" - {p}")
        else:
            print("저장된 파일이 없습니다.")
    else:
        path = scrape_hani_category(args.category, max_items=args.number)
        if path:
            print(f"완료: {path}")
        else:
            print("저장된 파일이 없습니다.")


if __name__ == "__main__":
    main()
