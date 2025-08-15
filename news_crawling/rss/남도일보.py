import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging
import os
from lxml import html


class NamdoTVRSSCollector:
    def __init__(self):
        self.base_url = "http://www.namdotv.net"
        self.rss_urls = {"전체기사": "http://www.namdotv.net/rss/allArticle.xml"}

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
            handlers=[logging.FileHandler("namdotv_rss.log", encoding="utf-8"), logging.StreamHandler()],
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
        """주어진 XPath에서 기사 본문만 추출하고 기자명은 고정 반환"""
        try:
            response = requests.get(article_url, headers=self.get_random_headers(), timeout=10)
            response.raise_for_status()

            # 인코딩 추정 보정
            try:
                response.encoding = response.apparent_encoding or response.encoding
            except Exception:
                pass

            tree = html.fromstring(response.content)

            # 1) 지정된 XPath에서 본문 추출
            xpath_candidates = [
                "/html/body/table/tbody/tr/td/div[7]/table[1]/tbody/tr/td[1]/div/div[5]/div[1]",
                # tbody 생략 버전 (파서에 따라 tbody 자동 삽입 이슈 대비)
                "/html/body/table/tr/td/div[7]/table[1]/tr/td[1]/div/div[5]/div[1]",
                # 보다 완화된 후보들: 기사 본문에 흔히 쓰이는 id/class 기반
                "//div[contains(@id,'article') or contains(@class,'article')][.//text()]",
                "//div[contains(@id,'content') or contains(@class,'content')][.//text()]",
            ]

            content = ""
            for xp in xpath_candidates:
                try:
                    nodes = tree.xpath(xp)
                except Exception:
                    nodes = []
                # 가장 텍스트가 긴 노드를 선택
                if nodes:
                    best_node = max(nodes, key=lambda n: len((n.text_content() or "").strip()))
                    content = (best_node.text_content() or "").strip()
                    if len(content) > 50:
                        break

            # 2) 여전히 비어있으면 BeautifulSoup 기반 폴백: 가장 긴 div 텍스트 선택
            if not content or len(content) < 50:
                try:
                    soup = BeautifulSoup(response.content, "lxml")
                    divs = soup.find_all("div")
                    # 노이즈 필터 키워드
                    noise_keywords = [
                        "저작권",
                        "무단",
                        "전재",
                        "재배포",
                        "공유",
                        "프린트",
                        "댓글",
                        "이전",
                        "다음",
                        "관련기사",
                        "태그",
                        "SNS",
                        "카카오톡",
                        "페이스북",
                        "트위터",
                        "메일",
                    ]

                    def is_noise(text):
                        t = (text or "").strip()
                        if len(t) < 80:
                            return True
                        return any(k in t for k in noise_keywords)

                    best_text = ""
                    for d in divs:
                        t = d.get_text(separator=" ", strip=True)
                        if not is_noise(t) and len(t) > len(best_text):
                            best_text = t
                    content = best_text
                except Exception:
                    pass

            # 공백 정리 최종 정제
            content = re.sub(r"\s+", " ", content or "").strip()

            reporter = "남도일보TV"
            return content, reporter
        except Exception as e:
            self.logger.error(f"기사 내용 추출 실패 - {article_url}: {str(e)}")
            return "", "남도일보TV"

    def collect_rss_data(self, category="전체기사", max_articles=20):
        """RSS 데이터 수집 (전체기사 위주, 기본 20건)"""
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
                    self.logger.info(
                        f"기사 처리 중 {i+1}/{min(len(feed.entries), max_articles)}: {getattr(entry, 'title', '')}"
                    )

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

                    # 기사 본문 및 추가 기자 정보 추출
                    content, _ = self.extract_article_content(link)
                    reporter = "남도일보TV"

                    article_data = {
                        "언론사": "남도일보",
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
        """CSV 파일로 저장 (results/남도일보_전체_{타임스탬프}.csv)"""
        if not articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 스크립트 위치 기준 results 디렉토리 생성
            results_dir = os.path.join(os.path.dirname(__file__), "results")
            os.makedirs(results_dir, exist_ok=True)
            filename = os.path.join(results_dir, f"남도일보_전체_{timestamp}.csv")

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
        """(사용 안 함) 모든 카테고리 수집 - 호환성 유지용"""
        return self.collect_rss_data("전체기사", max_articles_per_category)


def main():
    collector = NamdoTVRSSCollector()
    # 실행 시 바로 전체기사 20건 수집 및 저장
    articles = collector.collect_rss_data("전체기사", 20)
    collector.save_to_csv(articles)
    print(f"수집 완료: 총 {len(articles)}개 기사")


if __name__ == "__main__":
    main()
