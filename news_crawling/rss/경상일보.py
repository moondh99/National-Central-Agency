import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging


class KsilboRSSCollector:
    def __init__(self):
        self.base_url = "https://www.ksilbo.co.kr"
        self.rss_urls = {
            "전체기사": "https://www.ksilbo.co.kr/rss/allArticle.xml",
            "정치": "https://www.ksilbo.co.kr/rss/S1N1.xml",
            "경제": "https://www.ksilbo.co.kr/rss/S1N2.xml",
            "사회": "https://www.ksilbo.co.kr/rss/S1N3.xml",
            "문화": "https://www.ksilbo.co.kr/rss/S1N4.xml",
            "오피니언": "https://www.ksilbo.co.kr/rss/S1N8.xml",
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
            handlers=[logging.FileHandler("ksilbo_rss.log", encoding="utf-8"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 User-Agent가 포함된 헤더 반환"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def extract_article_content(self, article_url):
        """기사 본문 추출"""
        try:
            response = requests.get(article_url, headers=self.get_random_headers(), timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 특정 XPath에 해당하는 CSS 선택자로 기사 본문 추출
            # XPath: /html/body/div[1]/div/div[1]/div/div[1]/section/div[4]/div/section/article/div[2]/div/article[1]
            # CSS 선택자로 변환
            content_selectors = [
                "html body div:nth-of-type(1) div div:nth-of-type(1) div div:nth-of-type(1) section div:nth-of-type(4) div section article div:nth-of-type(2) div article:nth-of-type(1)",
                "body > div:nth-child(1) > div > div:nth-child(1) > div > div:nth-child(1) > section > div:nth-child(4) > div > section > article > div:nth-child(2) > div > article:nth-child(1)",
                ".article-content",  # 일반적인 기사 본문 클래스
                "article .content",
                ".news-content",
            ]

            content = ""
            article_element = None

            # 여러 선택자를 시도해서 본문 찾기
            for selector in content_selectors:
                try:
                    article_element = soup.select_one(selector)
                    if article_element:
                        content = article_element.get_text(strip=True)
                        if content and len(content) > 50:  # 최소 길이 확인
                            break
                except:
                    continue

            # 선택자로 찾지 못한 경우 전체 페이지에서 추출
            if not content or len(content) < 50:
                page_text = soup.get_text()
                content = page_text

            # 불필요한 텍스트 제거
            unwanted_patterns = [
                r"경상일보.*?ksilbo\.co\.kr",
                r"저작권자.*?무단전재.*?재배포.*?금지",
                r"개의\s*댓글",
                r"댓글\s*정렬",
                r"BEST댓글.*?자동으로\s*노출됩니다\.",
                r"댓글삭제.*?삭제하시겠습니까\?",
                r"댓글수정.*?가능합니다\.",
                r"홈.*?정치.*?경제.*?사회.*?문화",  # 네비게이션
                r"^\s*경상일보\s*$",
                r"^\s*울산지역.*?신문매체\.\s*$",
                r"기사입력.*?\d{4}\.\d{2}\.\d{2}",
                r"수정.*?\d{4}\.\d{2}\.\d{2}",
                r"프린트.*?스크랩.*?글자크기",
                r"페이스북.*?트위터.*?카카오스토리",
                r"([가-힣]{2,4})\s*기자",  # 본문에서 기자명 제거
            ]

            for pattern in unwanted_patterns:
                content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)

            # 텍스트 정제
            content = re.sub(r"\s+", " ", content)  # 연속된 공백 정리
            content = re.sub(r"\n+", "\n", content)  # 연속된 줄바꿈 정리
            content = content.strip()

            # 첫 번째 완전한 문장부터 시작하도록 조정
            sentences = re.split(r"[.!?]", content)
            if len(sentences) > 1:
                # 첫 문장이 너무 짧으면(메타데이터일 가능성) 제거
                if len(sentences[0]) < 10:
                    content = ".".join(sentences[1:]).strip()
                    if content.startswith("."):
                        content = content[1:].strip()

            return content, ""

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

                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, "published"):
                        try:
                            pub_date = entry.published
                        except:
                            pub_date = ""

                    # RSS에서 기자명 추출
                    reporter = ""
                    if hasattr(entry, "author"):
                        try:
                            # author 필드에서 기자명 추출
                            author_text = entry.author
                            # "기자" 앞의 이름 추출
                            reporter_match = re.search(r"([가-힣]{2,4})\s*기자", author_text)
                            if reporter_match:
                                reporter = reporter_match.group(1)
                            else:
                                # 기자가 없으면 전체 author 텍스트 사용
                                reporter = author_text.strip()
                        except:
                            reporter = ""

                    # 기사 본문 추출
                    content, _ = self.extract_article_content(link)

                    # 요약 (첫 200자)
                    summary = content[:200] + "..." if len(content) > 200 else content

                    article_data = {
                        "언론사": "경상일보",
                        "제목": title,
                        "날짜": pub_date,
                        "카테고리": category,
                        "기자명": reporter,
                        "본문": content,
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
            filename = f"results/경상일보_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = [
                    "언론사",
                    "제목",
                    "날짜",
                    "카테고리",
                    "기자명",
                    "본문",
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
    collector = KsilboRSSCollector()

    print("=== 경상일보 RSS 수집기 ===")
    print("수집 대상 카테고리: 전체기사, 정치, 경제, 사회, 문화, 오피니언")
    print("각 카테고리별 20개씩 수집을 시작합니다...")

    # 자동으로 지정된 카테고리들 수집
    articles = collector.collect_all_categories(20)
    collector.save_to_csv(articles)

    print(f"수집 완료: 총 {len(articles)}개 기사")


if __name__ == "__main__":
    main()
