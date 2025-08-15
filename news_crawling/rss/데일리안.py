import time, re, json
from urllib.parse import urljoin, urlparse
import csv
from datetime import datetime

import requests
from bs4 import BeautifulSoup

try:
    from readability import Document
except ImportError:
    Document = None

BASE = "https://www.dailian.co.kr"
# 카테고리 매핑: 요청에 따라 수정됨
CATEGORY_MAP = {
    "정치": "politics",
    "사회": "society",
    "경제": "economy",
    "생활/문화": "lifeCulture",
    "IT/과학": "itScience",
    "세계": "world",
    "수도권": "capital",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
}


def get_article_links(category, page=1):
    if category not in CATEGORY_MAP:
        print(f"지원하지 않는 카테고리입니다: {category}")
        return []
    list_url = f"{BASE}/{CATEGORY_MAP[category]}"
    params = {"page": page} if page > 1 else {}
    r = requests.get(list_url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # 전체기사 영역 한정
    container = soup.select_one("#body #contentsArea")
    if not container:
        return []

    # 제목 링크만 수집 (중복 제거 목적)
    a_tags = container.select(".itemContainer .marginTop20 .wide1Box p.listTitle2 a[href^='/news/view/']")
    links = []
    for a in a_tags:
        href = a.get("href", "")
        if href and href.startswith("/news/view/"):
            links.append(urljoin(BASE, href))

    # 중복 제거
    out, seen = [], set()
    for u in links:
        u_norm = urlparse(u)._replace(query="", fragment="").geturl()
        if u_norm not in seen:
            seen.add(u_norm)
            out.append(u_norm)
    return out


ARTICLE_BODY_SELECTORS = [
    "#articleBody",
    ".article-body",
    ".articleBody",
    ".article-content",
    ".article-contents",
    ".view_txt",
    ".article-txt",
    ".article_txt",
    "#articleView",
    "#article_body",
]


def clean_text(text: str) -> str:
    text = re.sub(r"\u200b|\xa0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def try_extract_with_selectors(html):
    soup = BeautifulSoup(html, "lxml")
    title = None
    for sel in ["article h1", "h1.title", "h1.tit", "#articleTitle", "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            title = el.get("content") if el.name == "meta" else el.get_text(strip=True)
            if title:
                break

    body = None
    for sel in ARTICLE_BODY_SELECTORS:
        el = soup.select_one(sel)
        if not el:
            continue
        # 불필요한 요소 제거
        for bad in el.select("script, style, figure, iframe, .ad, .advert, .sns, .share, .promotion"):
            bad.decompose()
        parts = []
        for tag in el.find_all(["p", "div", "li", "span"]):
            t = tag.get_text(" ", strip=True)
            if t:
                parts.append(t)
        body = clean_text("\n".join(parts))
        if len(body) > 200:
            break
    # 새로운 추출 로직: 원문 페이지의 지정된 위치에서 description 요소를 통한 본문 추출
    if not body or len(body) < 200:
        desc_selector = "html > body > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div > div:nth-of-type(1) > div:nth-of-type(4) > div:nth-of-type(1) > div > description"
        desc_el = soup.select_one(desc_selector)
        if desc_el:
            candidate = clean_text(desc_el.get_text(" ", strip=True))
            if candidate and len(candidate) > (len(body) if body else 0):
                body = candidate
    return title, body


def extract_article(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    title, body = try_extract_with_selectors(r.text)

    # 2차: 간소화된 뷰 시도
    if not body or len(body) < 200:
        light_url = url + ("&watchtype=light" if "?" in url else "?watchtype=light")
        try:
            r2 = requests.get(light_url, headers=HEADERS, timeout=20)
            if r2.ok:
                t2, b2 = try_extract_with_selectors(r2.text)
                title = title or t2
                if b2 and len(b2) > (len(body) if body else 0):
                    body = b2
        except Exception:
            pass

    # 3차: readability fallback
    if (not body or len(body) < 200) and Document is not None:
        try:
            doc = Document(r.text)
            content_html = doc.summary(html_partial=True)
            soup_doc = BeautifulSoup(content_html, "lxml")
            txt = "\n".join([p.get_text(" ", strip=True) for p in soup_doc.find_all(["p", "li"])])
            txt = clean_text(txt)
            if len(txt) > (len(body) if body else 0):
                body = txt
        except Exception:
            pass

    # 제목 보완
    if not title:
        m = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
        if m:
            title = m.group(1).strip()

    # 새로운 메타데이터 추출: 날짜와 기자명
    soup = BeautifulSoup(r.text, "lxml")
    meta_date = soup.find("meta", property="article:published_time")
    date = meta_date.get("content", "") if meta_date else ""

    meta_author = soup.find("meta", {"name": "author"})
    reporter = meta_author.get("content", "") if meta_author else ""
    if not reporter:
        reporter_elem = soup.select_one(
            "html > body > div:nth-of-type(1) > div:nth-of-type(1) > div > div:nth-of-type(2) > div > div > div:nth-of-type(1) > p"
        )
        if reporter_elem:
            reporter = reporter_elem.get_text(strip=True)

    return {"url": url, "title": title, "body": body, "date": date, "reporter": reporter}


def crawl(category, max_pages=3, delay=0.6):
    if category not in CATEGORY_MAP:
        print(f"지원하지 않는 카테고리입니다: {category}")
        return
    all_results = []
    seen_urls = set()
    for page in range(1, max_pages + 1):
        links = get_article_links(category, page)
        if not links:
            break
        print(f"[페이지 {page}] 링크 {len(links)}건")
        for u in links:
            if u in seen_urls:
                continue
            seen_urls.add(u)
            try:
                art = extract_article(u)
                body_len = len(art["body"] or "")
                print(f"- {art['title'] or '(제목없음)'} | {body_len}자 | {u}")
                all_results.append(art)
            except Exception as e:
                print("  에러:", u, e)
            time.sleep(delay)

    return all_results


if __name__ == "__main__":
    all_results_total = []
    for category in CATEGORY_MAP.keys():
        print(f"--- {category} 카테고리 크롤링 시작 ---")
        articles = crawl(category, max_pages=5)
        for art in articles:
            art["source"] = "데일리안"
            art["category"] = category
        all_results_total.extend(articles)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"results/데일리안_전체_{timestamp}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["언론사", "제목", "날짜", "카테고리", "기자명", "본문"])
        for art in all_results_total:
            writer.writerow([art["source"], art["title"], art["date"], art["category"], art["reporter"], art["body"]])
    print("저장 완료:", out_path, f"총 {len(all_results_total)}건")
