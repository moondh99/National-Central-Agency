import requests
from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
import time
from urllib.parse import urljoin


def extract_mbc_article_content(url):
    """MBC 뉴스 기사 URL에서 전체 본문을 추출하는 함수"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        # MBC 뉴스 기사 본문 추출 (다양한 선택자 시도)
        content_selectors = [
            "div.news-content",  # 뉴스 컨텐츠
            "div.article-content",  # 기사 컨텐츠
            "div.content",  # 컨텐츠
            "div.article-body",  # 기사 본문
            "div.news-text",  # 뉴스 텍스트
            ".news_txt",  # 뉴스 텍스트 클래스
            "div.view-content",  # 뷰 컨텐츠
            "#content",  # ID 기반 컨텐츠
            "div.text_area",  # 텍스트 영역
            "section.article-content",  # 섹션 기사 컨텐츠
            "div.detail-content",  # 상세 컨텐츠
        ]

        full_content = ""

        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    # 불필요한 요소들 제거
                    for unwanted in element.find_all(
                        [
                            "script",
                            "style",
                            "iframe",
                            "ins",
                            "div.ad",
                            ".advertisement",
                            ".related-articles",
                            ".tags",
                            ".share",
                            ".comment",
                            ".footer",
                            "div.reporter",
                            ".reporter_info",
                            ".social",
                            ".video",
                            ".photo",
                            ".image",
                            ".btn",
                        ]
                    ):
                        unwanted.decompose()

                    # 텍스트 추출
                    text = element.get_text(separator="\n", strip=True)
                    if text and len(text) > len(full_content):
                        full_content = text
                        break

                if full_content:
                    break

        # 본문이 여전히 짧다면 전체 페이지에서 텍스트 추출
        if len(full_content) < 100:
            # MBC 기사의 경우 HTML 구조가 다를 수 있으므로 전체 텍스트에서 추출
            page_text = soup.get_text(separator="\n", strip=True)

            # 기사 시작과 끝을 찾기
            start_markers = ["◀ 앵커 ▶", "◀ 리포트 ▶", "[앵커]", "[기자]"]
            end_markers = ["MBC 뉴스는 24시간", "▷ 전화", "▷ 이메일", "▷ 카카오톡"]

            lines = page_text.split("\n")
            content_lines = []
            in_content = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 기사 시작 마커 찾기
                if any(marker in line for marker in start_markers):
                    in_content = True
                    content_lines.append(line)
                    continue

                # 기사 끝 마커 찾기
                if any(marker in line for marker in end_markers):
                    break

                if in_content:
                    # 불필요한 라인 제외
                    if (
                        not line.startswith("▷")
                        and not line.startswith("※")
                        and "MBC" not in line
                        and "제보" not in line
                        and len(line) > 5
                    ):
                        content_lines.append(line)

            if content_lines:
                full_content = "\n".join(content_lines)

        # 텍스트 정리
        if full_content:
            # MBC 관련 정보 및 제보 정보 제거
            full_content = re.sub(r"MBC 뉴스는 24시간.*?@mbc제보", "", full_content, flags=re.DOTALL)
            full_content = re.sub(r"▷ 전화.*?카카오톡.*?@mbc제보", "", full_content, flags=re.DOTALL)
            full_content = re.sub(r"영상취재:.*?영상편집:.*?$", "", full_content, flags=re.MULTILINE)
            # 기자명 라인 제거 (마지막에 있는 경우)
            full_content = re.sub(r"\n[가-힣]{2,4}\s*(기자|특파원).*?$", "", full_content, flags=re.MULTILINE)
            # 연속된 공백과 줄바꿈 정리
            full_content = re.sub(r"\n+", "\n", full_content)
            full_content = re.sub(r"\s+", " ", full_content)
            full_content = full_content.strip()

        return full_content

    except Exception as e:
        print(f"본문 추출 중 오류: {e}")
        return ""


def extract_mbc_reporter_name(soup, article_text):
    """MBC 뉴스 기자명을 추출하는 함수"""
    try:
        # MBC 뉴스의 기자명 추출 패턴
        reporter_patterns = [
            # HTML에서 기자명 추출
            r"<span[^>]*class[^>]*reporter[^>]*>([^<]+)</span>",
            r"<div[^>]*class[^>]*reporter[^>]*>([^<]+)</div>",
            r"<p[^>]*class[^>]*reporter[^>]*>([^<]+)</p>",
            # 텍스트에서 기자명 추출 (MBC 특성에 맞게)
            r"MBC뉴스\s*([가-힣]{2,4})입니다",  # MBC뉴스 김재용입니다
            r"([가-힣]{2,4})\s*(기자|특파원)입니다",
            r"에서\s*MBC뉴스\s*([가-힣]{2,4})입니다",  # 워싱턴에서 MBC뉴스 김재용입니다
            r"([가-힣]{2,4})\s*(기자|특파원)(?:\s*=|\s*∙|\s*·|\s*입력|\s*수정|\s*작성)",
            r"기자\s*([가-힣]{2,4})(?:\s*=|\s*∙|\s*·)",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*앵커",
            r"([가-힣]{2,4})\s*논설위원",
            r"([가-힣]{2,4})\s*편집위원",
            r"/\s*([가-힣]{2,4})\s*기자",
            r"=\s*([가-힣]{2,4})\s*기자",
            r"∙\s*([가-힣]{2,4})\s*기자",
            r"·\s*([가-힣]{2,4})\s*기자",
            r"기자\s*:\s*([가-힣]{2,4})",
            r"\[([가-힣]{2,4})\s*기자\]",
            r"^([가-힣]{2,4})\s*기자",  # 줄 시작에서 기자명
            r"취재\s*:\s*([가-힣]{2,4})",  # 취재: 기자명
            r"영상취재\s*:\s*([가-힣]{2,4})",  # 영상취재: 기자명
        ]

        # BeautifulSoup 객체에서 기자명 찾기
        if soup:
            # 기자명이 포함될 가능성이 있는 요소들 찾기
            reporter_elements = soup.find_all(["span", "div", "p"], string=re.compile(r"기자|특파원|앵커"))
            for element in reporter_elements:
                text = element.get_text(strip=True)
                if ("기자" in text or "특파원" in text or "앵커" in text) and "MBC" in text:
                    match = re.search(r"([가-힣]{2,4})", text)
                    if match:
                        name = match.group(1)
                        if "기자" in text:
                            return name + " 기자"
                        elif "특파원" in text:
                            return name + " 특파원"
                        elif "앵커" in text:
                            return name + " 앵커"

        # 기사 텍스트에서 기자명 찾기
        full_text = str(soup) + "\n" + article_text if soup else article_text

        for pattern in reporter_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                if isinstance(matches[0], tuple):
                    reporter = matches[0][0].strip()
                    role = matches[0][1] if len(matches[0]) > 1 else "기자"
                else:
                    reporter = matches[0].strip()
                    role = "기자"

                if reporter and len(reporter) >= 2:
                    return reporter + f" {role}" if role not in reporter else reporter

        return "기자명 없음"

    except Exception as e:
        print(f"기자명 추출 중 오류: {e}")
        return "기자명 없음"


def get_mbc_news_list(base_url="https://imnews.imbc.com", categories=None, max_pages=3):
    """MBC 뉴스 목록을 가져오는 함수. categories 리스트 지정 시 해당 카테고리만 수집"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        news_items = []

        # 카테고리별 URL 패턴 (categories 지정 시 해당 카테고리만 사용)
        suffix_map = {
            "politics": "politics",
            "society": "society",
            "economy": "econo",
            "international": "world",
            "culture": "culture",
            "sports": "sports",
        }
        if categories:
            category_urls = [f"{base_url}/news/2025/{suffix_map.get(cat, cat)}/" for cat in categories]
        else:
            # 기본: 모든 카테고리와 메인 페이지 포함
            all_cats = list(suffix_map.values())
            category_urls = [f"{base_url}/news/2025/{cat}/" for cat in all_cats]
            category_urls.insert(0, f"{base_url}/")

        for category_url in category_urls:
            try:
                print(f"📄 {category_url} 페이지 뉴스 목록을 가져오는 중...")

                response = requests.get(category_url, headers=headers, timeout=15)
                response.encoding = "utf-8"
                soup = BeautifulSoup(response.text, "html.parser")

                # 뉴스 링크들 찾기 (다양한 선택자 시도)
                link_selectors = [
                    'a[href*="/article/"]',  # 기사 링크
                    'a[href*="_"]',  # MBC 기사 링크 패턴
                    "h3 a, h2 a, .title a",  # 제목 링크
                    ".news-list a",  # 뉴스 리스트 링크
                    ".headline a",  # 헤드라인 링크
                    ".article-list a",  # 기사 리스트 링크
                ]

                page_links = []
                for selector in link_selectors:
                    links = soup.select(selector)
                    if links:
                        page_links.extend(links)

                # 중복 제거 및 유효한 링크만 선별
                seen_urls = set()
                for link in page_links:
                    href = link.get("href")
                    if href and ("article" in href or "_" in href.split("/")[-1]):
                        full_url = urljoin(base_url, href)
                        if full_url not in seen_urls and "imnews.imbc.com" in full_url:
                            seen_urls.add(full_url)

                            # 제목 추출
                            title = link.get_text(strip=True)
                            if not title:
                                # 부모 요소에서 제목 찾기
                                title_elem = link.find_parent().find(["h1", "h2", "h3", "h4"])
                                if title_elem:
                                    title = title_elem.get_text(strip=True)

                            if title and len(title) > 5:  # 너무 짧은 제목 제외
                                news_items.append({"url": full_url, "title": title[:100]})  # 제목 길이 제한

                print(f"  ➤ 페이지에서 뉴스 발견")
                time.sleep(1)  # 페이지 요청 간 딜레이

            except Exception as e:
                print(f"  ➤ 카테고리 페이지 처리 중 오류: {e}")
                continue

        # 중복 제거
        unique_news = []
        seen_urls = set()
        for item in news_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_news.append(item)

        print(f"📊 총 {len(unique_news)}개의 고유한 뉴스를 발견했습니다.")
        return unique_news

    except Exception as e:
        print(f"뉴스 목록 수집 중 오류: {e}")
        return []


def scrape_mbc_news(max_articles=50, categories=None):
    """MBC 뉴스를 크롤링하여 CSV로 저장하는 메인 함수"""

    print("🗞️  MBC 뉴스 크롤링 시작")
    print("=" * 60)

    try:
        # 뉴스 목록 가져오기
        news_list = get_mbc_news_list(categories=categories)

        if not news_list:
            print("❌ 뉴스 목록을 가져올 수 없습니다.")
            return None

        news_data = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print(f"\n📰 {len(news_list)}개 기사의 상세 정보를 수집합니다...")

        for i, news_item in enumerate(news_list):
            try:
                url = news_item["url"]
                base_title = news_item["title"]

                print(f"[{i+1}/{len(news_list)}] 처리 중: {base_title[:50]}...")

                # 개별 기사 페이지 크롤링
                response = requests.get(url, headers=headers, timeout=20)
                response.encoding = "utf-8"
                soup = BeautifulSoup(response.text, "html.parser")

                # 제목 추출 (더 정확한 제목)
                title = base_title
                title_selectors = ["h1.title", "h1", ".news_title", ".article_title", "title"]
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        extracted_title = title_elem.get_text(strip=True)
                        if extracted_title and len(extracted_title) > len(title):
                            title = extracted_title
                        break

                # 날짜 추출 (URL이나 페이지에서)
                date_text = "날짜 없음"

                # URL에서 날짜 추출 시도
                url_date_match = re.search(r"/(\d{4})/|(\d{4})[-/](\d{1,2})[-/](\d{1,2})", url)
                if url_date_match:
                    if url_date_match.group(1):  # /2025/ 형태
                        date_text = f"{url_date_match.group(1)}-{datetime.now().month:02d}-{datetime.now().day:02d}"
                    else:  # 2025-06-28 형태
                        year, month, day = url_date_match.groups()[1:]
                        date_text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                # 페이지에서 날짜 추출 시도
                page_text = soup.get_text()
                date_patterns = [
                    r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
                    r"(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{2})",
                    r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
                    r"(\d{4})/(\d{1,2})/(\d{1,2})",
                ]

                for pattern in date_patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        groups = match.groups()
                        if len(groups) >= 3:
                            year, month, day = groups[0], groups[1], groups[2]
                            if len(groups) >= 5:
                                hour, minute = groups[3], groups[4]
                                date_text = f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute}"
                            else:
                                date_text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        break

                if date_text == "날짜 없음":
                    date_text = datetime.now().strftime("%Y-%m-%d %H:%M")

                # 전체 본문 추출
                full_content = extract_mbc_article_content(url)

                # 기자명 추출
                reporter_name = extract_mbc_reporter_name(soup, full_content)

                # 데이터 저장
                if full_content.strip():  # 본문이 있는 경우만 저장
                    news_data.append(
                        {"제목": title.strip(), "날짜": date_text, "기자명": reporter_name, "본문": full_content}
                    )
                else:
                    print(f"  ➤ 본문을 추출할 수 없어 건너뜁니다.")

                # 서버 부하 방지
                time.sleep(1.5)

            except Exception as e:
                print(f"  ➤ 기사 처리 중 오류: {e}")
                continue

        # CSV 파일로 저장은 메인에서 처리
        # 통계 정보 출력
        total_chars = sum(len(item["본문"]) for item in news_data)
        avg_chars = total_chars // len(news_data) if news_data else 0
        print(f"📊 평균 본문 길이: {avg_chars:,}자")
        print(f"📊 총 본문 길이: {total_chars:,}자")
        # 뉴스 데이터 리스트 반환
        return news_data
    except Exception as e:
        print(f"❌ 크롤링 중 오류 발생: {e}")
        return []


def scrape_mbc_by_category(category=None):
    """특정 카테고리의 MBC 뉴스 크롤링"""

    category_mapping = {
        "politics": "정치",
        "society": "사회",
        "economy": "경제",
        "international": "국제",
        "culture": "문화",
        "sports": "스포츠",
    }

    if category and category not in category_mapping:
        print(f"❌ 지원하지 않는 카테고리입니다.")
        print(f"✅ 지원 카테고리: {', '.join(category_mapping.keys())}")
        return None

    if category:
        print(f"📰 MBC {category_mapping[category]} 뉴스를 수집합니다.")
    else:
        print("📰 MBC 전체 뉴스를 수집합니다.")

    # 해당 카테고리만 수집 (제한 없이 전체 수집)
    return scrape_mbc_news(categories=[category] if category else None)


if __name__ == "__main__":
    # 자동으로 각 카테고리별 20개 기사 수집 후 하나의 CSV로 저장
    categories = [
        ("politics", "정치"),
        ("society", "사회"),
        ("economy", "경제"),
        ("international", "국제"),
        ("culture", "문화"),
    ]
    all_articles = []
    for key, kor in categories:
        print(f"\n=== MBC {kor} 뉴스 수집 시작 ===")
        data = scrape_mbc_by_category(key)
        for item in data:
            item["카테고리"] = kor
        all_articles.extend(data)
    # CSV 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/MBC_전체_{timestamp}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        # 언론사, 제목, 날짜, 카테고리, 기자명, 본문
        writer.writerow(["언론사", "제목", "날짜", "카테고리", "기자명", "본문"])
        for art in all_articles:
            writer.writerow(
                [
                    "MBC",  # 언론사
                    art.get("제목", ""),
                    art.get("날짜", ""),
                    art.get("카테고리", ""),
                    "mbc",  # 기자명 통일
                    art.get("본문", ""),
                ]
            )
    print(f"\n✅ MBC 뉴스 {len(all_articles)}개 자동 저장 완료: {filename}")
