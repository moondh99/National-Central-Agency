import requests
import xml.etree.ElementTree as ET
import csv
import re
from datetime import datetime
from bs4 import BeautifulSoup
import time
import os


def extract_mediatoday_article_content(url):
    """미디어오늘 기사 URL에서 전체 본문을 추출하는 함수"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        # 미디어오늘 기사 본문 추출 (다양한 선택자 시도)
        content_selectors = [
            'article[itemprop="articleBody"]',  # 메인 본문 요소
            "article#article-view-content-div",  # ID 기반 본문
            "div.article-body",  # 기사 본문
            "div.article_content",  # 기사 컨텐츠
            "div.news-content",  # 뉴스 컨텐츠
            "div.content",  # 컨텐츠
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
                            "div.related",
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
            # 미디어오늘의 경우 간단한 HTML 구조
            page_text = soup.get_text(separator="\n", strip=True)
            lines = page_text.split("\n")

            content_lines = []
            start_found = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 본문 시작 조건 (제목 이후)
                if not start_found:
                    # 이미지 캡션으로 시작하는 경우가 많음
                    if line.startswith("▲") or (
                        len(line) > 30
                        and not line.startswith("[")
                        and not line.startswith("Copyright")
                        and "미디어오늘" not in line
                        and "기자" not in line[-20:]
                    ):
                        start_found = True
                        content_lines.append(line)
                    continue

                # 본문 끝 조건
                if (
                    line.startswith("Copyright")
                    or line.startswith("▶")
                    or line.startswith("▷")
                    or "저작권자" in line
                    or "무단전재" in line
                    or "재배포 금지" in line
                    or "관련기사" in line
                ):
                    break

                # 유효한 본문 라인 추가
                if len(line) > 5:
                    content_lines.append(line)

            if content_lines:
                full_content = "\n".join(content_lines)

        # 텍스트 정리
        if full_content:
            # 저작권 관련 정보 제거
            full_content = re.sub(r"Copyright.*?미디어오늘.*?금지", "", full_content, flags=re.DOTALL)
            full_content = re.sub(r"▶.*?미디어오늘.*?$", "", full_content, flags=re.MULTILINE)
            full_content = re.sub(r"관련기사.*?$", "", full_content, flags=re.DOTALL)
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


def extract_mediatoday_reporter_name(soup, article_text):
    """미디어오늘 기자명을 추출하는 함수"""
    try:
        # 미디어오늘의 기자명 추출 패턴
        reporter_patterns = [
            # HTML에서 기자명 추출
            r"<span[^>]*class[^>]*reporter[^>]*>([^<]+)</span>",
            r"<div[^>]*class[^>]*reporter[^>]*>([^<]+)</div>",
            # 텍스트에서 기자명 추출 (미디어오늘 특성에 맞게)
            r"([가-힣]{2,4})\s*(기자|특파원)(?:\s*=|\s*∙|\s*·|\s*입력|\s*수정|\s*작성)",
            r"기자\s*([가-힣]{2,4})(?:\s*=|\s*∙|\s*·)",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*편집위원",
            r"([가-힣]{2,4})\s*논설위원",
            r"/\s*([가-힣]{2,4})\s*기자",
            r"=\s*([가-힣]{2,4})\s*기자",
            r"∙\s*([가-힣]{2,4})\s*기자",
            r"·\s*([가-힣]{2,4})\s*기자",
            r"기자\s*:\s*([가-힣]{2,4})",
            r"\[([가-힣]{2,4})\s*기자\]",
            r"취재\s*:\s*([가-힣]{2,4})",  # 취재: 기자명
            r"글\s*:\s*([가-힣]{2,4})",  # 글: 기자명
            r"정리\s*:\s*([가-힣]{2,4})",  # 정리: 기자명
        ]

        # BeautifulSoup 객체에서 기자명 찾기
        if soup:
            # 기자명이 포함될 가능성이 있는 요소들 찾기
            reporter_elements = soup.find_all(["span", "div", "p"], string=re.compile(r"기자|특파원|취재|정리"))
            for element in reporter_elements:
                text = element.get_text(strip=True)
                if "기자" in text or "특파원" in text:
                    match = re.search(r"([가-힣]{2,4})", text)
                    if match:
                        name = match.group(1)
                        if "기자" in text:
                            return name + " 기자"
                        elif "특파원" in text:
                            return name + " 특파원"

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


def parse_mediatoday_rss_full_content(category="all", max_articles=20):
    """미디어오늘 RSS를 파싱하여 전체 본문과 함께 CSV로 저장하는 함수"""

    # 미디어오늘 RSS URL 목록
    category_urls = {
        "all": "https://www.mediatoday.co.kr/rss/allArticle.xml",
        "society": "https://www.mediatoday.co.kr/rss/S1N4.xml",  # 사회
        "opinion": "https://www.mediatoday.co.kr/rss/S1N7.xml",  # 오피니언
    }

    if category not in category_urls:
        print(f"❌ 지원하지 않는 카테고리입니다.")
        print(f"✅ 지원 카테고리: {', '.join(category_urls.keys())}")
        return None

    rss_url = category_urls[category]

    try:
        print(f"📡 미디어오늘 {category} RSS 피드를 가져오는 중...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"

        # XML 파싱
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        total_items = len(items)
        print(f"총 {total_items}개의 뉴스 항목을 발견했습니다. 최대 {max_articles}개만 처리합니다.")
        items = items[:max_articles]
        news_data = []

        print(f"총 {len(items)}개의 뉴스 항목을 발견했습니다.")
        print("각 기사의 전체 본문을 추출하는 중... (시간이 소요될 수 있습니다)")

        for i, item in enumerate(items):
            try:
                # 기본 정보 추출
                title = item.find("title").text if item.find("title") is not None else "제목 없음"
                title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)
                title = re.sub(r"<[^>]+>", "", title).strip()

                # 링크 추출
                link = item.find("link").text if item.find("link") is not None else ""

                # 날짜 추출
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                formatted_date = ""
                if pub_date:
                    try:
                        # 미디어오늘 RSS 날짜 형식: 2025-06-28 15:22:32
                        date_obj = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
                        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_date = pub_date
                else:
                    formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M")

                print(f"[{i+1}/{len(items)}] 처리 중: {title[:60]}...")

                if link:
                    # 전체 본문 추출
                    try:
                        article_response = requests.get(link, headers=headers, timeout=20)
                        article_response.encoding = "utf-8"
                        soup = BeautifulSoup(article_response.text, "html.parser")

                        # 전체 본문 추출
                        full_content = extract_mediatoday_article_content(link)
                        # 기자명: RSS author 태그 우선
                        author_tag = item.find("author")
                        if author_tag is not None and author_tag.text:
                            reporter_name = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", author_tag.text).strip()
                        else:
                            reporter_name = extract_mediatoday_reporter_name(soup, full_content)

                        # 본문이 너무 짧은 경우 RSS description도 포함
                        if len(full_content) < 200:
                            rss_description = (
                                item.find("description").text if item.find("description") is not None else ""
                            )
                            rss_description = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", rss_description)
                            rss_description = re.sub(r"<[^>]+>", "", rss_description).strip()

                            if rss_description:
                                full_content = (
                                    rss_description + "\n\n" + full_content if full_content else rss_description
                                )

                        # 데이터 저장
                        if full_content.strip():  # 본문이 있는 경우만 저장
                            news_data.append(
                                {"제목": title, "날짜": formatted_date, "기자명": reporter_name, "본문": full_content}
                            )
                        else:
                            print(f"  ➤ 본문을 추출할 수 없어 건너뜁니다.")

                        # 서버 부하 방지
                        time.sleep(1)

                    except Exception as e:
                        print(f"  ➤ 기사 처리 중 오류: {e}")
                        # 오류가 발생해도 RSS 기본 정보는 저장
                        description = item.find("description").text if item.find("description") is not None else ""
                        description = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", description)
                        description = re.sub(r"<[^>]+>", "", description).strip()

                        news_data.append(
                            {"제목": title, "날짜": formatted_date, "기자명": "기자명 없음", "본문": description}
                        )
                        continue

            except Exception as e:
                print(f"RSS 항목 처리 중 오류: {e}")
                continue

        # 파싱된 데이터를 리스트로 반환
        return news_data

    except Exception as e:
        print(f"❌ RSS 파싱 중 오류 발생: {e}")
        return []


def scrape_mediatoday_multiple_categories(categories=["all"], max_articles_per_category=20):
    """여러 카테고리의 미디어오늘 뉴스를 동시에 수집하는 함수"""

    print("🗞️  미디어오늘 다중 카테고리 수집")
    print("=" * 60)

    # 통합 데이터를 저장할 리스트
    combined_data = []

    for category in categories:
        print(f"\n📰 {category} 카테고리 처리 중...")
        try:
            items = parse_mediatoday_rss_full_content(category, max_articles_per_category)
            if items:
                for item in items:
                    combined_data.append(
                        {
                            "언론사": "미디어오늘",
                            "제목": item.get("제목", ""),
                            "날짜": item.get("날짜", ""),
                            "카테고리": category,
                            "기자명": item.get("기자명", ""),
                            "본문": item.get("본문", ""),
                        }
                    )
                print(f"✅ {category} 카테고리 완료 ({len(items)}개)")
            else:
                print(f"❌ {category} 카테고리 데이터 없음")
        except Exception as e:
            print(f"❌ {category} 카테고리 처리 중 오류: {e}")
            continue

    # CSV 저장
    if combined_data:
        os.makedirs("results", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results/미디어오늘_전체_{ts}.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(combined_data)
        print(f"\n🎉 저장 완료: {filename} ({len(combined_data)}건)")
        return filename
    else:
        print("❌ 수집된 데이터가 없습니다.")
        return None


if __name__ == "__main__":
    # 자동으로 모든 카테고리에 대해 최대 20개씩 수집
    default_categories = ["all", "society", "opinion"]
    print("🗞️ 미디어오늘 RSS 자동 크롤링 시작 (각 카테고리 최대 20개)")
    scrape_mediatoday_multiple_categories(default_categories, max_articles_per_category=20)
