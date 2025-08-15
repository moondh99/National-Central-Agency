import feedparser
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import csv
import time
import random
from datetime import datetime
import re


class KoreaTimesRSSCollector:
    def __init__(self):
        self.base_url = "https://www.koreatimes.co.kr"
        self.rss_feeds = {
            "All News": "https://feed.koreatimes.co.kr/k/allnews.xml",
            "Foreign Affairs": "https://feed.koreatimes.co.kr/k/foreignaffairs.xml",
            "South Korea": "https://feed.koreatimes.co.kr/k/southkorea.xml",
            "Business": "https://feed.koreatimes.co.kr/k/business.xml",
            "World": "https://feed.koreatimes.co.kr/k/world.xml",
        }

        # User-Agent 리스트 (랜덤 선택용)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

    def get_random_user_agent(self):
        return random.choice(self.user_agents)

    def clean_text(self, text):
        """텍스트 정제 함수"""
        if not text:
            return ""

        # HTML 태그 제거
        text = re.sub(r"<[^>]+>", "", text)
        # CDATA 제거
        text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
        # 특수문자 정제
        text = re.sub(r"&nbsp;|&lt;|&gt;|&amp;|&quot;|&#39;", " ", text)
        # 여러 공백을 하나로
        text = re.sub(r"\s+", " ", text)
        # 앞뒤 공백 제거
        text = text.strip()

        return text

    def extract_reporter_name(self, text, author_info=None):
        """기자명 추출 함수"""
        if not text and not author_info:
            return ""

        # author 정보에서 먼저 추출 시도
        if author_info:
            # 이메일에서 기자명 추출
            email_patterns = [r"([a-zA-Z0-9]+)@koreatimes\.co\.kr", r"([a-zA-Z]+)@koreatimes\.co\.kr"]

            for pattern in email_patterns:
                match = re.search(pattern, author_info)
                if match:
                    return match.group(1)

        # 본문에서 기자명 패턴 추출
        if text:
            patterns = [
                r"By\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",  # By FirstName LastName
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*staff\s*writer",
                r"([가-힣]{2,4})\s*기자",
                r"기자\s*([가-힣]{2,4})",
                r"Staff\s+writer\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*@koreatimes\.co\.kr",
            ]

            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)

        return ""

    def get_article_content(self, url):
        """개별 기사 본문 추출"""
        try:
            # Selenium 헤드리스 브라우저로 페이지 로드 (경고창 및 로깅 제거)
            options = Options()
            options.add_argument("--headless")  # 헤드리스 모드
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-infobars")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            # 서비스 로그를 /dev/null로 리디렉션하고 ChromeDriverManager로 드라이버 설치
            service = Service(ChromeDriverManager().install(), log_path=os.devnull)
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(url)
            # 페이지 소스 불러와 항상 soup 생성
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            # 상대 XPath로 우선 본문 추출
            elems = driver.find_elements(
                By.XPATH, "//div[@data-article-content='true']//p[contains(@class,'editor-p')]"
            )
            if elems:
                content = " ".join([el.text.strip() for el in elems if el.text.strip()])
            else:
                # CSS selector 대체 본문 추출
                container = soup.select_one('div[data-article-content="true"]')
                if container:
                    paras = container.find_all("p", class_=re.compile(r"editor-p"))
                    content = " ".join([p.get_text(strip=True) for p in paras if p.get_text(strip=True)])
                else:
                    # 기본 selector 사용
                    content = ""
                    content_selectors = [
                        "article .article-content",
                        ".article-content",
                        ".news-content",
                        "#article-content",
                        ".articleCont",
                        ".article_cont",
                        'div[itemprop="articleBody"]',
                        ".article-body",
                        ".content-body",
                        ".story-body",
                    ]
                    for sel in content_selectors:
                        el = soup.select_one(sel)
                        if el:
                            content = el.get_text(strip=True)
                            break
                if not content:
                    # 모든 단락 합치기
                    paras = soup.find_all("p")
                    content = " ".join([p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 20])
            driver.quit()

            # 기자명 추출
            reporter = ""
            reporter_selectors = [
                ".reporter",
                ".byline",
                ".author",
                ".article-info",
                ".news-info",
                ".writer-info",
                ".story-byline",
            ]

            for selector in reporter_selectors:
                reporter_element = soup.select_one(selector)
                if reporter_element:
                    reporter_text = reporter_element.get_text()
                    reporter = self.extract_reporter_name(reporter_text)
                    if reporter:
                        break

            return self.clean_text(content), reporter

        except Exception as e:
            print(f"본문 추출 실패 ({url}): {e}")
            return "", ""

    def collect_rss_feed(self, category, rss_url):
        """RSS 피드에서 기사 수집"""
        articles = []

        try:
            print(f"\n{category} RSS 피드 수집 중...")

            # RSS 피드 파싱
            feed = feedparser.parse(rss_url)

            if not feed.entries:
                print(f"RSS 피드가 비어있습니다: {rss_url}")
                return articles

            # RSS 피드에서 최대 20개 기사만 처리
            for entry in feed.entries[:20]:
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    description = self.clean_text(entry.get("description", ""))
                    pub_date = entry.get("published", "")
                    author = entry.get("author", "")

                    # 발행일 파싱
                    try:
                        if pub_date:
                            # RSS 날짜 포맷: Sun, 03 Aug 2025 06:27:03 GMT
                            parsed_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                            formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 개별 기사 본문 추출
                    if link:
                        content, _ = self.get_article_content(link)
                        time.sleep(random.uniform(0.5, 1.5))  # 요청 간격 조절
                    else:
                        content = description
                    # RSS author에서 기자명 추출
                    reporter = self.extract_reporter_name("", author)

                    article_data = {
                        "source": "KoreaTimes",
                        "title": title,
                        "pub_date": formatted_date,
                        "category": category,
                        "reporter": reporter,
                        "content": content,
                    }

                    articles.append(article_data)
                    print(f"수집완료: {title[:50]}...")

                except Exception as e:
                    print(f"기사 처리 중 오류: {e}")
                    continue

        except Exception as e:
            print(f"RSS 피드 수집 실패 ({rss_url}): {e}")

        return articles

    def save_to_csv(self, articles, filename):
        """CSV 파일로 저장"""
        if not articles:
            print("저장할 기사가 없습니다.")
            return

        # 언론사, 제목, 날짜, 카테고리, 기자명, 본문 순서
        fieldnames = [
            "언론사",
            "제목",
            "날짜",
            "카테고리",
            "기자명",
            "본문",
        ]

        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            # 헤더 기록
            writer.writerow(fieldnames)
            # 각 article dict에서 값 순서대로 추출하여 기록
            for art in articles:
                row = [
                    art.get("source", ""),
                    art.get("title", ""),
                    art.get("pub_date", ""),
                    art.get("category", ""),
                    art.get("reporter", ""),
                    art.get("content", ""),
                ]
                writer.writerow(row)

        print(f"\n총 {len(articles)}개 기사가 {filename}에 저장되었습니다.")

    def run_collection(self, selected_categories=None):
        """전체 수집 실행"""
        print("=" * 60)
        print("Korea Times RSS 뉴스 수집기")
        print("=" * 60)

        # 모든 RSS 피드 카테고리에 대해 최대 20개 기사 수집
        all_articles = []
        for category, rss_url in self.rss_feeds.items():
            articles = self.collect_rss_feed(category, rss_url)
            all_articles.extend(articles)
            time.sleep(2)  # 카테고리 간 대기시간

        # 결과 저장
        if all_articles:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/KoreaTimes_전체_{timestamp}.csv"
            self.save_to_csv(all_articles, filename)

            # 수집 결과 요약
            print("\n" + "=" * 60)
            print("수집 결과 요약")
            print("=" * 60)

            category_counts = {}
            for article in all_articles:
                category = article["category"]
                category_counts[category] = category_counts.get(category, 0) + 1

            for category, count in category_counts.items():
                print(f"{category}: {count}개")

            print(f"\n전체: {len(all_articles)}개 기사 수집 완료")
            print(f"파일명: {filename}")
        else:
            print("수집된 기사가 없습니다.")


def main():
    """메인 실행 함수"""
    collector = KoreaTimesRSSCollector()

    # 사용 예시 1: 기본 카테고리 수집
    collector.run_collection()


if __name__ == "__main__":
    main()
