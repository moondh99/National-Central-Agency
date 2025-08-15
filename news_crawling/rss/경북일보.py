import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging


class KyongbukRSSCollector:
    def __init__(self):
        self.base_url = "https://www.kyongbuk.co.kr"
        self.rss_urls = {
            "전체기사": "https://www.kyongbuk.co.kr/rss/allArticle.xml",
            "경북대구": "https://www.kyongbuk.co.kr/rss/S1N1.xml",
            "정치": "https://www.kyongbuk.co.kr/rss/S1N3.xml",
            "경제": "https://www.kyongbuk.co.kr/rss/S1N4.xml",
            "사회": "https://www.kyongbuk.co.kr/rss/S1N5.xml",
            "경북일보TV": "https://www.kyongbuk.co.kr/rss/S2N87.xml",
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
            handlers=[logging.FileHandler("kyongbuk_rss.log", encoding="utf-8"), logging.StreamHandler()],
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

            # 기사 본문 추출 - 지정된 XPath 경로 사용
            content = ""

            # XPath: /html/body/div[2]/div/div[1]/div/div[1]/section/div[4]/div/section/article/div[2]/div/article[1]/p
            # CSS 선택자로 변환하여 사용
            article_paragraphs = soup.select(
                "body > div:nth-child(2) > div > div:nth-child(1) > div > div:nth-child(1) > section > div:nth-child(4) > div > section > article > div:nth-child(2) > div > article:nth-child(1) > p"
            )

            if article_paragraphs:
                # 모든 p 태그의 텍스트를 수집
                content_parts = []
                for p in article_paragraphs:
                    text = p.get_text(strip=True)
                    if text:  # 빈 문자열이 아닌 경우만 추가
                        content_parts.append(text)
                content = " ".join(content_parts)
            else:
                # 지정된 경로에서 찾을 수 없는 경우 대안 방법 사용
                # 더 일반적인 선택자로 본문 찾기
                alternative_selectors = [
                    "article p",
                    ".article-content p",
                    ".news-content p",
                    "#article-view-content-div p",
                ]

                for selector in alternative_selectors:
                    paragraphs = soup.select(selector)
                    if paragraphs:
                        content_parts = []
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if text and len(text) > 10:  # 최소 길이 체크
                                content_parts.append(text)
                        if content_parts:
                            content = " ".join(content_parts)
                            break

            # 텍스트 정제
            if content:
                content = re.sub(r"\s+", " ", content)  # 연속된 공백 정리

                # 불필요한 텍스트 제거
                unwanted_patterns = [
                    r"기자명\s+[가-힣]{2,4}\s*기자",
                    r"승인\s+\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}",
                    r"지면게재일\s+\d{4}년\s+\d{2}월\s+\d{2}일\s+[가-힣]+요일",
                    r"댓글\s+\d+",
                    r"저작권자.*?무단전재.*?재배포.*?금지",
                    r"개의\s*댓글",
                    r"댓글\s*정렬",
                    r"BEST댓글.*?자동으로\s*노출됩니다\.",
                    r"댓글삭제.*?삭제하시겠습니까\?",
                    r"댓글수정.*?가능합니다\.",
                    r"홈경북대구경북구미사회사건사고",
                ]

                for pattern in unwanted_patterns:
                    content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)

                # 최종 정제
                content = content.strip()

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

                    # RSS에서 기자명 추출
                    reporter = ""
                    if hasattr(entry, "author"):
                        author_text = entry.author
                        # "서의수 기자" 형태에서 기자명만 추출
                        reporter_match = re.search(r"([가-힣]{2,4})\s*기자", author_text)
                        if reporter_match:
                            reporter = reporter_match.group(1)
                        else:
                            # 기자명만 있는 경우
                            reporter = author_text.strip()

                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, "published"):
                        try:
                            pub_date = entry.published
                        except:
                            pub_date = ""

                    # 기사 본문 추출
                    content, _ = self.extract_article_content(link)

                    article_data = {
                        "언론사": "경북일보",
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
            filename = f"results/경북일보_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
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
    collector = KyongbukRSSCollector()

    print("=== 경북일보 RSS 수집기 ===")
    print("전체기사, 경북대구, 정치, 경제, 사회, 경북일보TV 카테고리에서 각각 20개씩 수집을 시작합니다...")

    # 지정된 6개 카테고리에서 각각 20개씩 자동 수집
    articles = collector.collect_all_categories(20)
    collector.save_to_csv(articles)

    print(f"수집 완료: 총 {len(articles)}개 기사")


if __name__ == "__main__":
    main()
