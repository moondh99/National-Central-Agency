import requests
import feedparser
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime
import time
import re
from urllib.parse import urljoin

# 뉴시스 RSS 피드 URL 딕셔너리
rss_feeds = {
    "속보": "https://www.newsis.com/RSS/sokbo.xml",
    "정치": "https://www.newsis.com/RSS/politics.xml",
    "경제": "https://www.newsis.com/RSS/economy.xml",
    "사회": "https://www.newsis.com/RSS/society.xml",
    "국제": "https://www.newsis.com/RSS/international.xml",
    "문화": "https://www.newsis.com/RSS/culture.xml",
    "금융": "https://www.newsis.com/RSS/bank.xml",
    "산업": "https://www.newsis.com/RSS/industry.xml",
    "수도권": "https://www.newsis.com/RSS/met.xml",
    "지방": "https://www.newsis.com/RSS/country.xml",
}


def get_article_content(url):
    """뉴시스 기사 URL에서 본문과 기자명을 추출하는 함수"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # 본문 추출 (지정된 XPath: /html/body/div[1]/div[5]/div[5]/div[1]/div[1]/div[3]/article)
        content = ""
        content_selectors = [
            "html > body > div:nth-child(1) > div:nth-child(5) > div:nth-child(5) > div:nth-child(1) > div:nth-child(1) > div:nth-child(3) > article",
            "article",
            "div.article_text",
            "div.article-body",
            '[class*="article"]',
            '[class*="content"]',
        ]

        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                content = content_element.get_text(strip=True)
                if content and len(content) > 50:  # 충분한 길이의 본문만 사용
                    break

        # 기자명 추출 - 다양한 패턴으로 시도
        reporter = ""
        reporter_text = soup.get_text()

        # 기자명 패턴 추출
        reporter_patterns = [
            r"([가-힣]+)\s*기자",
            r"기자\s*([가-힣]+)",
            r"([가-힣]+\s+[가-힣]+)\s*기자",
            r"기자\s*=\s*([가-힣]+)",
            r"=\s*([가-힣]+)\s*기자",
        ]

        for pattern in reporter_patterns:
            match = re.search(pattern, reporter_text)
            if match:
                reporter = match.group(1).strip() + " 기자"
                break

        # 추가 기자명 추출 시도
        if not reporter:
            reporter_selectors = [
                '[class*="reporter"]',
                '[class*="author"]',
                '[class*="writer"]',
                ".journalist",
                ".byline",
            ]

            for selector in reporter_selectors:
                reporter_element = soup.select_one(selector)
                if reporter_element:
                    reporter_text = reporter_element.get_text(strip=True)
                    if reporter_text and len(reporter_text) < 50:
                        reporter = reporter_text
                        break

        return content, reporter

    except Exception as e:
        print(f"기사 내용 추출 실패 ({url}): {str(e)}")
        return "", ""


def collect_news_from_rss(category, rss_url, max_articles=20):
    """RSS 피드에서 뉴스를 수집하는 함수"""
    try:
        print(f"\n{category} 카테고리 수집 중...")

        # RSS 피드 파싱
        feed = feedparser.parse(rss_url)

        if not feed.entries:
            print(f"  {category}: RSS 피드에서 데이터를 가져올 수 없습니다.")
            return []

        articles = []
        collected_count = 0

        for entry in feed.entries[:max_articles]:
            if collected_count >= max_articles:
                break

            try:
                # 기본 정보 추출
                title = entry.title if hasattr(entry, "title") else ""
                link = entry.link if hasattr(entry, "link") else ""
                pub_date = entry.published if hasattr(entry, "published") else ""

                if not title or not link:
                    continue

                # 날짜 파싱
                try:
                    if pub_date:
                        # feedparser가 자동으로 파싱한 날짜 사용
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            date_obj = datetime(*entry.published_parsed[:6])
                            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            formatted_date = pub_date
                    else:
                        formatted_date = ""
                except:
                    formatted_date = pub_date

                # 기사 본문과 기자명 추출
                content, reporter = get_article_content(link)

                article_data = {
                    "언론사": "뉴시스",
                    "제목": title,
                    "날짜": formatted_date,
                    "카테고리": category,
                    "기자명": reporter,
                    "본문": content,
                }

                articles.append(article_data)
                collected_count += 1

                print(f"  {category}: {collected_count}/{max_articles} 수집 완료")

                # 서버 부하 방지를 위한 딜레이
                time.sleep(0.5)

            except Exception as e:
                print(f"  {category}: 기사 처리 중 오류 - {str(e)}")
                continue

        print(f"  {category}: 총 {len(articles)}개 기사 수집 완료")
        return articles

    except Exception as e:
        print(f"{category} 카테고리 수집 실패: {str(e)}")
        return []


def main():
    """메인 실행 함수"""
    print("뉴시스 RSS 피드 수집을 시작합니다...")
    print(f"총 {len(rss_feeds)}개 카테고리에서 각각 20개씩 수집합니다.")

    # results 디렉토리 생성
    os.makedirs("results", exist_ok=True)

    all_articles = []

    # 각 RSS 피드에서 뉴스 수집
    for category, rss_url in rss_feeds.items():
        articles = collect_news_from_rss(category, rss_url, max_articles=20)
        all_articles.extend(articles)

        # 카테고리간 딜레이
        time.sleep(1)

    if not all_articles:
        print("수집된 기사가 없습니다.")
        return None

    # DataFrame 생성
    df = pd.DataFrame(all_articles)

    # 컬럼 순서 정렬
    column_order = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
    df = df[column_order]

    # 파일명 생성 (타임스탬프 포함)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/뉴시스_전체_{timestamp}.csv"

    # CSV 파일 저장 (UTF-8 BOM 인코딩으로 Excel 호환성 확보)
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"\n=== 수집 완료 ===")
    print(f"총 수집 기사 수: {len(all_articles)}개")
    print(f"저장된 파일: {filename}")
    print(f"파일 크기: {os.path.getsize(filename):,} 바이트")


# 실행
if __name__ == "__main__":
    result_file = main()
