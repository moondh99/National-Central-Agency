import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import csv
import time
import random
import logging
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse


class DailyNewsCrawler:
    def __init__(self):
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("daily_news_rss_crawler.log", encoding="utf-8"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

        # 데일리뉴스 RSS 피드 목록
        self.rss_feeds = {"전체기사": "https://www.idailynews.co.kr/rss/allArticle.xml"}

        # User-Agent 목록
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

        self.articles = []

    def get_random_headers(self):
        """랜덤 User-Agent 헤더 반환"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }

    def clean_text(self, text):
        """텍스트 정제 함수"""
        if not text:
            return ""

        # CDATA 태그 제거
        text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)

        # HTML 태그 제거
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()

        # 불필요한 텍스트 제거
        unwanted_texts = [
            "데일리뉴스 제공",
            "무단전재 및 재배포 금지",
            "Copyright by Daily News",
            "저작권자",
            "▶ 데일리뉴스",
            "홈페이지에서 확인하세요",
            "뉴스룸 제보",
            "무단 전재-재배포",
            "ⓒ데일리뉴스",
        ]

        for unwanted in unwanted_texts:
            text = text.replace(unwanted, "")

        # 여러 공백을 하나로 변환
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract_reporter_name(self, title, description=""):
        """RSS 제목과 description에서 기자명 추출"""
        # 제목과 description을 합쳐서 검색
        combined_text = f"{title} {description}"

        # 데일리뉴스 기자명 패턴들
        patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*논설위원",
            r"([가-힣]{2,4})\s*편집위원",
            r"데일리뉴스\s*([가-힣]{2,4})",
            r"리포터\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*리포터",
        ]

        for pattern in patterns:
            match = re.search(pattern, combined_text)
            if match:
                return match.group(1) + " 기자"

        return "기자명 없음"

    def format_date(self, date_str):
        """날짜 형식 변환"""
        try:
            # RFC 2822 형식 파싱 시도
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            try:
                # GMT 없는 형식 시도
                dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                try:
                    # KST 형식 시도
                    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S KST")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    try:
                        # +0900 형식 시도
                        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S +0900")
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        try:
                            # 다른 형식 시도
                            dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
                            return dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            return date_str

    def get_content_from_description(self, description):
        """RSS description에서 내용 추출"""
        if not description:
            return "RSS description 없음"

        # description 정제
        content = self.clean_text(description)

        # 너무 짧은 경우
        if len(content) < 20:
            return "RSS description이 너무 짧음"

        return content

    def get_article_content_fallback(self, url):
        """본문 추출 시도 (fallback)"""
        try:
            headers = self.get_random_headers()
            session = requests.Session()
            session.headers.update(headers)

            response = session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 새 명시적 셀렉터 사용하여 본문 추출 시도
            specific_selector = "html > body > div:nth-of-type(1) > div > div:nth-of-type(1) > div > div:nth-of-type(1) > section > div:nth-of-type(5) > article > section > article > article:nth-of-type(1) > section > article:nth-of-type(1)"
            content_elem = soup.select_one(specific_selector)
            if content_elem:
                content = self.clean_text(content_elem.get_text())
                if content and len(content.strip()) > 30:
                    return content

            # 기존 데일리뉴스 본문 셀렉터들
            content_selectors = [
                "div.article_content p",
                ".article_content p",
                "div.news_body p",
                ".news_body p",
                "div.article_body p",
                ".article_body p",
                "div.entry-content p",
                ".entry-content p",
                # 전체 영역
                "div.article_content",
                ".article_content",
                "div.news_body",
                ".news_body",
                "div.article_body",
                ".article_body",
            ]

            content = ""

            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    if "p" in selector:
                        paragraphs = []
                        for elem in elements:
                            text = elem.get_text().strip()
                            if len(text) > 20 and not any(
                                skip in text
                                for skip in [
                                    "저작권자",
                                    "Copyright",
                                    "무단전재",
                                    "재배포 금지",
                                    "데일리뉴스 제공",
                                    "뉴스룸 제보",
                                ]
                            ):
                                paragraphs.append(text)

                        if paragraphs:
                            content = " ".join(paragraphs[:3])
                            break
                    else:
                        for elem in elements:
                            text = elem.get_text()
                            if len(text.strip()) > 50:
                                content = text
                                break

                if content and len(content.strip()) > 50:
                    break

            # 내용 정제
            content = self.clean_text(content)

            if content and len(content.strip()) > 30:
                return content

            return "본문 추출 실패"

        except Exception as e:
            self.logger.warning(f"본문 추출 실패 ({url}): {e}")
            return "본문 추출 실패"

    def parse_rss_feed(self, category, url):
        """RSS 피드 파싱"""
        try:
            self.logger.info(f"{category} RSS 피드 크롤링 시작: {url}")

            headers = self.get_random_headers()
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # 응답이 비어있는지 확인
            if not response.content.strip():
                self.logger.error(f"{category} RSS 피드가 비어있습니다: {url}")
                return []

            # XML 파싱
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                self.logger.error(f"{category} RSS XML 파싱 오류: {e}")
                return []

            # RSS 아이템 추출
            items = root.findall(".//item")

            if not items:
                self.logger.warning(f"{category} RSS 피드에서 아이템을 찾을 수 없습니다")
                return []

            articles = []

            # 최대 20개 기사 처리
            for i, item in enumerate(items[:20]):
                try:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pubdate_elem = item.find("pubDate")
                    description_elem = item.find("description")

                    if title_elem is None or link_elem is None:
                        continue

                    title = self.clean_text(title_elem.text)
                    link = link_elem.text.strip()
                    pub_date = self.format_date(pubdate_elem.text) if pubdate_elem is not None else ""
                    description = self.clean_text(description_elem.text) if description_elem is not None else ""

                    # 기자명 추출: rss author 태그 우선 사용
                    author_elem = item.find("author")
                    if author_elem is not None and author_elem.text:
                        reporter = self.clean_text(author_elem.text)
                    else:
                        reporter = self.extract_reporter_name(title, description)

                    # 원문 페이지에서 본문 직접 추출
                    self.logger.info(f"기사 처리 중: {title[:30]}... 원문 페이지에서 본문 직접 추출 시도")
                    content = self.get_article_content_fallback(link)
                    time.sleep(random.uniform(2, 4))  # 본문 추출 시 딜레이

                    article = {
                        "title": title,
                        "category": category,
                        "date": pub_date,
                        "reporter": reporter,
                        "content": content,
                        "url": link,
                    }

                    articles.append(article)

                    # 기본 딜레이
                    time.sleep(random.uniform(1, 2))

                except Exception as e:
                    self.logger.error(f"기사 처리 중 오류 발생: {e}")
                    continue

            self.logger.info(f"{category} 카테고리에서 {len(articles)}개 기사 수집 완료")
            return articles

        except requests.RequestException as e:
            self.logger.error(f"{category} RSS 피드 요청 오류: {e}")
            return []
        except Exception as e:
            self.logger.error(f"{category} RSS 피드 처리 중 오류: {e}")
            return []

    def crawl_all_feeds(self):
        """모든 RSS 피드 크롤링"""
        self.logger.info("데일리뉴스 RSS 크롤링 시작")

        for category, url in self.rss_feeds.items():
            self.logger.info(f"\n=== {category} 카테고리 크롤링 ===")

            articles = self.parse_rss_feed(category, url)
            self.articles.extend(articles)

            # 카테고리 간 딜레이
            time.sleep(random.uniform(3, 5))

        self.logger.info(f"\n총 {len(self.articles)}개 기사 수집 완료")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장 (변경된 형식)"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/데일리뉴스_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                # CSV 열 순서: 언론사, 제목, 날짜, 카테고리, 기자명, 본문
                fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in self.articles:
                    row = {
                        "언론사": "데일리뉴스",
                        "제목": article["title"],
                        "날짜": article["date"],
                        "카테고리": article["category"],
                        "기자명": article["reporter"],
                        "본문": article["content"],
                    }
                    writer.writerow(row)

            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            print(f"\n✅ 크롤링 완료! 결과 파일: {filename}")
            print(f"📊 총 수집된 기사: {len(self.articles)}개")

        except Exception as e:
            self.logger.error(f"CSV 파일 저장 실패: {e}")


def main():
    """메인 실행 함수"""
    crawler = DailyNewsCrawler()

    print("🚀 데일리뉴스 RSS 크롤링을 시작합니다...")
    print("📰 수집 대상 카테고리: 전체기사, 인기기사")
    print("📰 RSS Description 우선 활용, 필요시 본문 추출")
    print("⏳ 안정적인 크롤링을 위해 적절한 딜레이가 적용됩니다.\n")

    try:
        # RSS 피드 크롤링
        crawler.crawl_all_feeds()

        # CSV 파일로 저장
        crawler.save_to_csv()

        # 결과 요약 출력
        if crawler.articles:
            print(f"\n📋 카테고리별 수집 현황:")
            category_count = {}
            for article in crawler.articles:
                category = article["category"]
                category_count[category] = category_count.get(category, 0) + 1

            for category, count in category_count.items():
                print(f"   • {category}: {count}개")

    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 크롤링 중 오류 발생: {e}")
        logging.error(f"메인 실행 오류: {e}")


if __name__ == "__main__":
    main()
