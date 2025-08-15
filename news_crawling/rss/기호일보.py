import requests
import feedparser
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import os
import time
from urllib.parse import urljoin

# RSS URL 매핑 딕셔너리 (9개 카테고리)
rss_urls = {
    "전체기사": "https://www.kihoilbo.co.kr/rss/allArticle.xml",
    "정치": "https://www.kihoilbo.co.kr/rss/clickTop.xml",
    "경제": "https://www.kihoilbo.co.kr/rss/S1N2.xml",
    "사회": "https://www.kihoilbo.co.kr/rss/S1N4.xml",
    "문화": "https://www.kihoilbo.co.kr/rss/S1N5.xml",
    "교육": "https://www.kihoilbo.co.kr/rss/S1N6.xml",
    "지역": "https://www.kihoilbo.co.kr/rss/S1N7.xml",
    "종합": "https://www.kihoilbo.co.kr/rss/S1N8.xml",
    "오피니언": "https://www.kihoilbo.co.kr/rss/S1N11.xml",
}


def parse_rss_feed(url, category, max_articles=20):
    """
    RSS 피드에서 기사 정보를 파싱하는 함수

    Args:
        url (str): RSS 피드 URL
        category (str): 카테고리명
        max_articles (int): 최대 수집할 기사 수

    Returns:
        list: 기사 정보가 담긴 딕셔너리 리스트
    """
    articles = []

    try:
        # RSS 피드 파싱
        feed = feedparser.parse(url)

        if not feed.entries:
            print(f"[경고] {category} 카테고리에서 기사를 찾을 수 없습니다.")
            return articles

        for entry in feed.entries[:max_articles]:
            article_data = {
                "언론사": "키호일보",
                "제목": entry.get("title", "제목 없음"),
                "날짜": entry.get("published", "날짜 없음"),
                "카테고리": category,
                "기자명": entry.get("author", "기자명 없음"),
                "링크": entry.get("link", ""),
            }
            articles.append(article_data)

        print(f"[완료] {category} 카테고리: {len(articles)}개 기사 수집")

    except Exception as e:
        print(f"[오류] {category} RSS 파싱 중 오류 발생: {str(e)}")

    return articles


def extract_article_content(url, max_retries=3):
    """
    기사 URL에서 본문을 추출하는 함수

    Args:
        url (str): 기사 URL
        max_retries (int): 최대 재시도 횟수

    Returns:
        str: 추출된 본문 내용
    """
    if not url:
        return "URL 없음"

    for attempt in range(max_retries):
        try:
            # 웹페이지 요청
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # 지정된 XPath에 해당하는 CSS 선택자로 본문 추출
                # XPath: /html/body/div[1]/div/div[1]/div/div[1]/section/div[4]/div/section/article/div[2]/div/article[1]
                # CSS 선택자로 변환
                content_selectors = [
                    "body > div:nth-child(1) > div > div:nth-child(1) > div > div:nth-child(1) > section > div:nth-child(4) > div > section > article > div:nth-child(2) > div > article:nth-child(1)",
                    "article div.article-content",
                    "div.article-content",
                    ".article_view",
                    "#articleText",
                    ".news_text",
                ]

                content = ""
                for selector in content_selectors:
                    element = soup.select_one(selector)
                    if element:
                        content = element.get_text(strip=True)
                        break

                if not content:
                    # 대안: p 태그들을 모아서 본문 추출 시도
                    paragraphs = soup.find_all("p")
                    content = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

                return content[:1000] + "..." if len(content) > 1000 else content if content else "본문 추출 실패"

            else:
                print(f"[경고] HTTP {response.status_code} 오류: {url}")

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # 1초 대기 후 재시도
                continue
            else:
                print(f"[오류] 본문 추출 실패 ({url}): {str(e)}")
                return "본문 추출 실패"

    return "본문 추출 실패"


def collect_all_news():
    """
    모든 카테고리에서 뉴스를 자동으로 수집하는 메인 함수

    Returns:
        list: 모든 기사 정보가 담긴 리스트
    """
    all_articles = []

    print("키호일보 뉴스 수집을 시작합니다...")
    print(f"총 {len(rss_urls)}개 카테고리에서 각각 20개씩 수집 예정\n")

    for i, (category, url) in enumerate(rss_urls.items(), 1):
        print(f"[{i}/{len(rss_urls)}] {category} 카테고리 수집 중...")

        # RSS에서 기사 목록 수집
        articles = parse_rss_feed(url, category, 20)

        if articles:
            # 각 기사의 본문 추출
            for j, article in enumerate(articles, 1):
                print(f"  - {j}/{len(articles)} 본문 추출 중: {article['제목'][:30]}...")

                # 본문 추출
                content = extract_article_content(article["링크"])
                article["본문"] = content

                # 진행률 표시를 위한 짧은 대기
                if j % 5 == 0:
                    time.sleep(0.5)

            all_articles.extend(articles)
            print(f"  → {category} 완료: {len(articles)}개 기사 수집\n")
        else:
            print(f"  → {category}: 수집된 기사 없음\n")

        # 카테고리 간 대기 (서버 부하 방지)
        if i < len(rss_urls):
            time.sleep(1)

    print(f"전체 수집 완료! 총 {len(all_articles)}개 기사 수집됨")
    return all_articles


def save_to_csv(articles):
    """
    수집된 기사를 CSV 파일로 저장하는 함수

    Args:
        articles (list): 기사 정보가 담긴 리스트
    """
    # results 디렉토리 생성
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    # 타임스탬프 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"기호일보_전체_{timestamp}.csv"
    filepath = os.path.join(results_dir, filename)

    # DataFrame 생성 (컬럼 순서: 언론사, 제목, 날짜, 카테고리, 기자명, 본문)
    df = pd.DataFrame(articles)

    # 컬럼 순서 재정렬
    column_order = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
    df = df[column_order]

    # CSV 파일로 저장 (UTF-8 인코딩)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    print(f"✅ CSV 파일 저장 완료!")
    print(f"파일 경로: {filepath}")
    print(f"파일 크기: {os.path.getsize(filepath):,} bytes")

    # 결과 요약
    print(f"\n📊 수집 결과 요약:")
    print(f"✅ 총 수집 기사 수: {len(df)}개")
    print(f"✅ 수집 카테고리: {len(df['카테고리'].unique())}개")

    print(f"\n📈 카테고리별 수집 현황:")
    category_counts = df["카테고리"].value_counts().sort_index()
    for category, count in category_counts.items():
        status = "✅" if count >= 15 else "⚠️" if count >= 10 else "❌"
        print(f"  {status} {category}: {count}개")

    return filepath


# 메인 실행 함수
def main():
    """
    메인 실행 함수
    """
    print("=" * 60)
    print("🎉 키호일보 뉴스 수집기 시작!")
    print("=" * 60)

    # 뉴스 수집
    collected_articles = collect_all_news()

    if collected_articles:
        # CSV 파일로 저장
        filepath = save_to_csv(collected_articles)

        print(f"\n📅 수집 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        return filepath
    else:
        print("❌ 수집된 기사가 없습니다.")
        return None


# 프로그램 실행
if __name__ == "__main__":
    # 필요한 라이브러리 설치 (처음 실행 시)
    # pip install feedparser requests beautifulsoup4 pandas lxml

    main()
