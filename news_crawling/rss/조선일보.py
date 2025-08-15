#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("chosun_scraping.log", encoding="utf-8"), logging.StreamHandler()],
)

# dc:creator를 위한 네임스페이스
NS = {"dc": "http://purl.org/dc/elements/1.1/"}

# 조선일보 RSS 피드 URL
RSS_FEEDS = {
    "전체기사": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "정치": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml",
    "경제": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml",
    "사회": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml",
    "국제": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml",
    "문화": "https://www.chosun.com/arc/outboundfeeds/rss/category/culture-life/?outputType=xml",
    "오피니언": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml",
}

# 초기 셀레니움 드라이버 설정 (헤드리스 Chrome)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)


def get_full_content(url):
    """기사 원문 페이지에서 본문 추출 (선택자 강화 + canonical 추적 1회)"""
    try:
        # Selenium으로 페이지 로드
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Canonical/OG URL 추적 (최대 1회)
        try:
            canon = soup.find("link", rel=lambda v: v and "canonical" in v)
            canon_href = canon.get("href") if canon else None
            if not canon_href:
                og = soup.find("meta", attrs={"property": "og:url"})
                canon_href = og.get("content") if og else None
            if canon_href:
                canon_url = urljoin(url, canon_href)
                if canon_url and canon_url != url and urlparse(canon_url).scheme in {"http", "https"}:
                    driver.get(canon_url)
                    soup = BeautifulSoup(driver.page_source, "html.parser")
        except Exception:
            pass

        # 본문 선택자 강화: 우선순위대로 탐색
        selectors = [
            'section.article-body[itemprop="articleBody"]',
            "section.article-body",
            '[itemprop="articleBody"]',
            "article .article-body",
            "div.article-body",
            "article",
        ]
        section = None
        for sel in selectors:
            section = soup.select_one(sel)
            if section:
                break
        if not section:
            return ""

        # 불필요 요소 제거 강화 (광고/이미지 래퍼 등)
        unwanted = [
            "script",
            "style",
            "nav",
            "aside",
            "footer",
            "header",
            "iframe",
            "ins",
            ".dfpAd",
            '[class*="ad"]',
            "figure",
            ".arcad-wrapper",
            "svg",
            "noscript",
            "picture",
            "source",
            ".related",
            '[class*="related"]',
            ".subscribe",
            '[class*="subscribe"]',
            ".share",
            '[class*="share"]',
            "button",
            "form",
        ]
        for sel in unwanted:
            for el in section.select(sel):
                try:
                    el.decompose()
                except Exception:
                    continue

        # 본문 단락 추출: 우선 조선일보 기본 클래스, 없으면 모든 <p>
        paras = section.select('p[class*="article-body__content-text"]')
        if not paras:
            paras = section.find_all("p")
        if paras:
            texts = [p.get_text(" ").strip() for p in paras if p.get_text().strip()]
            return "\n\n".join(texts)
        return section.get_text().strip()
    except Exception:
        return ""


def parse_rss_feed(rss_url, category):
    """RSS 피드를 불러와 최신 20개 기사를 파싱"""
    try:
        resp = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logging.error(f"{category} RSS 요청 실패: {e}")
        return []

    articles = []
    # 최신 20개 기사만 처리
    for item in root.findall(".//item")[:20]:
        # 제목
        title = (item.findtext("title") or "").strip()
        # 링크
        link = (item.findtext("link") or "").strip()
        # 날짜
        date = ""
        pub = item.findtext("pubDate")
        if pub:
            try:
                from dateutil import parser

                date = parser.parse(pub).strftime("%Y-%m-%d")
            except:
                date = datetime.now().strftime("%Y-%m-%d")
        # 기자명 (dc:creator)
        creator = item.find("dc:creator", NS)
        reporter = creator.text.replace("기자", "").strip() if creator is not None and creator.text else ""
        # 본문: 원문 페이지에서 추출
        full_text = get_full_content(link)
        # 원문 추출 실패 시 RSS 요약으로 대체
        if not full_text:
            desc = item.findtext("description") or ""
            full_text = BeautifulSoup(desc, "html.parser").get_text().strip()

        articles.append(
            {
                "언론사명": "조선일보",
                "제목": title,
                "날짜": date,
                "카테고리": category,
                "기자명": reporter,
                "본문": full_text,
            }
        )

    logging.info(f"{category}에서 {len(articles)}개 기사 수집 완료")
    return articles


def main():
    all_articles = []
    for cat, url in RSS_FEEDS.items():
        all_articles.extend(parse_rss_feed(url, cat))

    if not all_articles:
        logging.warning("수집된 기사가 없습니다.")
        return

    df = pd.DataFrame(all_articles)
    # 컬럼 순서 고정
    df = df[["언론사명", "제목", "날짜", "카테고리", "기자명", "본문"]]

    os.makedirs("results", exist_ok=True)
    fname = f"results/조선일보_전체_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(fname, index=False, encoding="utf-8-sig")

    print(f"수집 완료: {len(df)}개 기사, 저장 파일: {fname}")


if __name__ == "__main__":
    main()
