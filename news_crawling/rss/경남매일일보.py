import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging


class GDNNewsRSSCollector:
    def __init__(self):
        self.base_url = "http://www.gdnnews.com"
        self.rss_urls = {
            "전체기사": "http://www.gdnnews.com/rss/allArticle.xml",
            "뉴스": "http://www.gdnnews.com/rss/S1N1.xml",
        }

        # User-Agent 리스트 (랜덤 선택용)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("gdnnews_rss.log", encoding="utf-8"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 User-Agent가 포함된 헤더 반환"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def extract_article_content(self, article_url):
        """기사 본문과 기자 정보 추출"""
        try:
            response = requests.get(article_url, headers=self.get_random_headers(), timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 기사 본문 추출
            content = ""

            # 기사 본문 영역 찾기 (경남매일일보의 구조에 맞게)
            article_body = soup.find("div", {"id": "article-view-content-div"})
            if not article_body:
                article_body = soup.find("div", class_="news-content")
            if not article_body:
                article_body = soup.find("div", class_="article-content")
            if not article_body:
                # 텍스트가 포함된 div 찾기
                article_body = soup.find("div", string=re.compile(r".*기자.*"))
                if article_body:
                    article_body = article_body.parent

            if article_body:
                # 불필요한 요소들 제거
                for unwanted in article_body.find_all(["script", "style", "iframe", "ins", "aside", "nav"]):
                    unwanted.decompose()

                # 저작권 관련 텍스트 제거
                for copyright_text in article_body.find_all(string=re.compile(r"저작권자.*무단전재.*재배포.*금지")):
                    copyright_text.extract()

                # 텍스트 추출 및 정제
                content = article_body.get_text(strip=True)
                content = re.sub(r"\s+", " ", content)  # 연속된 공백 정리
                content = re.sub(r"\n+", "\n", content)  # 연속된 줄바꿈 정리

                # 저작권 관련 텍스트와 기타 불필요한 텍스트 제거
                content = re.sub(r"저작권자.*?무단전재.*?재배포.*?금지", "", content)
                content = re.sub(r"계정을 선택하시면.*?댓글을 남기실 수 있습니다\.", "", content)
                content = re.sub(r"\*\s*\*\s*\*", "", content)

            # 기자 정보 추출 (RSS와 본문에서)
            reporter = ""

            # RSS에서 이미 기자명이 있는 경우가 많음
            # 본문에서 추가 패턴 확인
            reporter_patterns = [
                r"\[([^=\]]+)=([가-힣]{2,4})\s*기자\]",  # [지역=기자명 기자] 패턴
                r"([가-힣]{2,4})\s*기자",
                r"기자\s+([가-힣]{2,4})",
                r"([가-힣]{2,4})\s*특파원",
                r"([가-힣]{2,4})\s*편집위원",
            ]

            for pattern in reporter_patterns:
                match = re.search(pattern, content)
                if match:
                    if len(match.groups()) > 1:  # [지역=기자명 기자] 패턴
                        reporter = match.group(2)
                    else:
                        reporter = match.group(1)
                    break

            # 이메일에서 기자명 추출 시도
            if not reporter:
                email_pattern = r"([a-zA-Z0-9._%+-]+)@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
                email_match = re.search(email_pattern, content)
                if email_match:
                    email_id = email_match.group(1)
                    # 이메일 아이디가 한글 기자명을 포함하는 경우 추출
                    korean_in_email = re.search(r"[가-힣]{2,4}", email_id)
                    if korean_in_email:
                        reporter = korean_in_email.group()

            return content, reporter

        except Exception as e:
            self.logger.error(f"기사 내용 추출 실패 - {article_url}: {str(e)}")
            return "", ""

    def collect_rss_data(self, category="전체기사", max_articles=50):
        """RSS 데이터 수집"""
        rss_url = self.rss_urls.get(category, self.rss_urls["전체기사"])
        self.logger.info(f"RSS 수집 시작: {category} - {rss_url}")

        try:
            # RSS 피드 파싱
            feed = feedparser.parse(rss_url)

            if not feed.entries:
                self.logger.warning(f"RSS 피드에서 데이터를 찾을 수 없습니다: {rss_url}")
                return []

            articles = []

            for i, entry in enumerate(feed.entries[:max_articles]):
                try:
                    self.logger.info(f"기사 처리 중 {i+1}/{min(len(feed.entries), max_articles)}: {entry.title}")

                    # 기본 정보 추출
                    title = entry.title if hasattr(entry, "title") else ""
                    link = entry.link if hasattr(entry, "link") else ""

                    # RSS에서 기자명 추출 (경남매일일보는 RSS에 기자명이 포함되어 있음)
                    rss_reporter = ""
                    if hasattr(entry, "author"):
                        rss_reporter = entry.author

                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, "published"):
                        try:
                            pub_date = entry.published
                        except:
                            pub_date = ""

                    # 기사 본문 및 추가 기자 정보 추출
                    content, content_reporter = self.extract_article_content(link)

                    # 기자명 결정 (RSS 우선, 본문에서 추출한 것 보조)
                    reporter = rss_reporter if rss_reporter else content_reporter

                    # 요약 (첫 200자)
                    summary = content[:200] + "..." if len(content) > 200 else content

                    article_data = {
                        "언론사": "경남매일일보",
                        "제목": title,
                        "날짜": pub_date,
                        "카테고리": category,
                        "기자명": reporter,
                        "본문": content,
                        "link": link,
                        "summary": summary,
                        "collected_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    articles.append(article_data)

                    # 요청 간격 조절 (서버 부하 방지)
                    time.sleep(random.uniform(1, 3))

                except Exception as e:
                    self.logger.error(f"개별 기사 처리 실패: {str(e)}")
                    continue

            self.logger.info(f"RSS 데이터 수집 완료: {len(articles)}개 기사")
            return articles

        except Exception as e:
            self.logger.error(f"RSS 피드 파싱 실패: {str(e)}")
            return []

    def save_to_csv(self, articles, filename=None):
        """CSV 파일로 저장"""
        if not articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/경남매일일보_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = [
                    "언론사",
                    "제목",
                    "날짜",
                    "카테고리",
                    "기자명",
                    "본문",
                    "link",
                    "summary",
                    "collected_date",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in articles:
                    writer.writerow(article)

            self.logger.info(f"CSV 파일 저장 완료: {filename}")

        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {str(e)}")

    def collect_all_categories(self, max_articles_per_category=20):
        """지정된 카테고리의 기사 수집"""
        all_articles = []

        for category in self.rss_urls.keys():
            self.logger.info(f"카테고리 '{category}' 수집 시작")
            articles = self.collect_rss_data(category, max_articles_per_category)
            all_articles.extend(articles)

            # 카테고리 간 대기 시간
            time.sleep(random.uniform(2, 5))

        return all_articles


def main():
    collector = GDNNewsRSSCollector()

    print("=== 경남매일일보 RSS 수집기 ===")
    print("전체기사, 뉴스 카테고리에서 각각 20개씩 수집을 시작합니다...")

    # 지정된 4개 카테고리에서 각각 20개씩 자동 수집
    articles = collector.collect_all_categories(20)
    collector.save_to_csv(articles)

    print(f"수집 완료: 총 {len(articles)}개 기사")


if __name__ == "__main__":
    main()
