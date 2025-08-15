import requests
import pandas as pd
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import os
from datetime import datetime
import time
import re

# RSS URL 매핑 딕셔너리 (9개 카테고리)
rss_urls = {
    "전체뉴스": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    "정치": "https://www.khan.co.kr/rss/rssdata/politic_news.xml",
    "경제": "https://www.khan.co.kr/rss/rssdata/economy_news.xml",
    "사회": "https://www.khan.co.kr/rss/rssdata/society_news.xml",
    "문화": "https://www.khan.co.kr/rss/rssdata/culture_news.xml",
    "지역": "https://www.khan.co.kr/rss/rssdata/local_news.xml",
    "오피니언": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml",
    "국제": "https://www.khan.co.kr/rss/rssdata/kh_world.xml",
    "사람": "https://www.khan.co.kr/rss/rssdata/people_news.xml",
}


def parse_rss_feed(rss_url, max_items=20):
    """RSS 피드를 파싱하여 뉴스 정보를 추출하는 함수"""
    try:
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()

        # XML 파싱
        root = ET.fromstring(response.content)

        items = []
        # item 태그들을 찾아서 처리
        for item in root.findall(".//item")[:max_items]:
            # 제목 추출
            title_elem = item.find("title")
            title = title_elem.text if title_elem is not None else ""
            if title.startswith("<![CDATA[") and title.endswith("]]>"):
                title = title[9:-3].strip()

            # 링크 추출
            link_elem = item.find("link")
            link = link_elem.text if link_elem is not None else ""

            # 날짜 추출 (dc:date 또는 pubDate)
            date_elem = item.find("{http://purl.org/dc/elements/1.1/}date")
            if date_elem is None:
                date_elem = item.find("pubDate")
            date = date_elem.text if date_elem is not None else ""

            # 기자명 추출 (author 태그에서)
            author_elem = item.find("author")
            author = author_elem.text if author_elem is not None else ""
            if author.startswith("<![CDATA[") and author.endswith("]]>"):
                author = author[9:-3].strip()

            items.append({"title": title, "link": link, "date": date, "author": author})

        return items

    except Exception as e:
        print(f"RSS 피드 파싱 오류: {e}")
        return []


def extract_article_content(url):
    """기사 URL에서 본문 내용을 추출하는 함수"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # 한국일보에 최적화된 선택자들 (우선순위 순)
        selectors = [
            '[class*="content"]',  # 발견된 최적 선택자
            ".art_txt",
            "main section:first-child article section div",
            ".article_txt",
            ".news_txt",
            ".content_area",
            "article p",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                # 가장 긴 텍스트를 가진 요소 선택
                best_content = ""
                for elem in elements:
                    text = elem.get_text(strip=True, separator=" ")
                    if len(text) > len(best_content) and len(text) > 100:  # 충분한 길이
                        best_content = text

                if best_content:
                    # 불필요한 공백 정리
                    content = re.sub(r"\s+", " ", best_content)
                    return content[:2000]  # 최대 2000자로 제한

        return "본문 추출 실패"

    except Exception as e:
        print(f"본문 추출 오류 ({url}): {e}")
        return f"본문 추출 오류: {str(e)}"


def collect_news_by_category(category, rss_url, max_items=20):
    """특정 카테고리의 뉴스를 수집하는 함수"""
    print(f"\n[{category}] 카테고리 뉴스 수집 중...")

    # RSS 피드에서 뉴스 목록 가져오기
    rss_items = parse_rss_feed(rss_url, max_items)

    if not rss_items:
        print(f"[{category}] RSS 피드에서 뉴스를 가져오지 못했습니다.")
        return []

    collected_news = []

    for i, item in enumerate(rss_items, 1):
        print(f"[{category}] {i}/{len(rss_items)} - {item['title'][:50]}...")

        # 본문 추출
        content = extract_article_content(item["link"])

        # 데이터 구성
        news_data = {
            "언론사": "한국일보",
            "제목": item["title"],
            "날짜": item["date"],
            "카테고리": category,
            "기자명": item["author"],
            "본문": content,
        }

        collected_news.append(news_data)

        # 서버 부하 방지를 위한 짧은 대기
        time.sleep(0.5)

    print(f"[{category}] 총 {len(collected_news)}개 뉴스 수집 완료")
    return collected_news


def collect_all_news():
    """모든 카테고리의 뉴스를 자동으로 수집하는 메인 함수"""
    print("=== 한국일보 뉴스 자동 수집 시작 ===")
    print(f"수집 대상: {len(rss_urls)}개 카테고리, 각 카테고리당 20개씩")
    print(f"예상 총 뉴스 개수: {len(rss_urls) * 20}개")

    all_news = []

    for category, url in rss_urls.items():
        try:
            category_news = collect_news_by_category(category, url, 20)
            all_news.extend(category_news)
        except Exception as e:
            print(f"[{category}] 수집 중 오류 발생: {e}")
            continue

    print(f"\n=== 수집 완료 ===")
    print(f"총 수집된 뉴스: {len(all_news)}개")

    return all_news


def save_to_csv(news_data):
    """수집된 뉴스 데이터를 CSV 파일로 저장하는 함수"""
    if not news_data:
        print("저장할 데이터가 없습니다.")
        return None

    # DataFrame 생성
    df = pd.DataFrame(news_data)

    # 열 순서 지정: 언론사, 제목, 날짜, 카테고리, 기자명, 본문
    column_order = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
    df = df[column_order]

    # results 디렉토리 생성
    os.makedirs("results", exist_ok=True)

    # 타임스탬프 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/한국일보_전체_{timestamp}.csv"

    # CSV 저장 (UTF-8 인코딩)
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"\nCSV 파일 저장 완료: {filename}")
    print(f"저장된 데이터: {len(df)}행 x {len(df.columns)}열")
    print(f"컬럼: {', '.join(df.columns)}")

    # 카테고리별 통계
    category_stats = df["카테고리"].value_counts()
    print(f"\n카테고리별 뉴스 개수:")
    for category, count in category_stats.items():
        print(f"  {category}: {count}개")

    return filename


def main():
    """메인 실행 함수"""
    start_time = time.time()

    print("🚀 한국일보 뉴스 자동 수집을 시작합니다!")
    print("=" * 60)

    # 모든 카테고리의 뉴스 수집
    all_collected_news = collect_all_news()

    # CSV 파일로 저장
    if all_collected_news:
        saved_filename = save_to_csv(all_collected_news)

        end_time = time.time()
        elapsed_time = end_time - start_time

        print(f"\n✅ 전체 프로세스 완료!")
        print(f"⏱️  소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
        print(f"📁 저장된 파일: {saved_filename}")
        print(f"📊 수집된 총 뉴스: {len(all_collected_news)}개")
    else:
        print("❌ 수집된 뉴스가 없습니다.")


if __name__ == "__main__":
    main()
