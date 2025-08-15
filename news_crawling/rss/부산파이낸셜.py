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


class BusanFinancialNewsCrawler:
    def __init__(self):
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("busan_financial_news_rss_crawler.log", encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

        # 부산파이낸셜뉴스 RSS 피드 목록
        self.rss_feeds = {
            "전체기사": "http://www.fnnews.com/rss/r20/fn_realnews_all.xml",
            "정치": "http://www.fnnews.com/rss/r20/fn_realnews_politics.xml",
            "국제": "http://www.fnnews.com/rss/r20/fn_realnews_international.xml",
            "사회": "http://www.fnnews.com/rss/r20/fn_realnews_society.xml",
            "경제": "http://www.fnnews.com/rss/r20/fn_realnews_economy.xml",
            "증권": "http://www.fnnews.com/rss/r20/fn_realnews_stock.xml",
            "금융": "http://www.fnnews.com/rss/r20/fn_realnews_finance.xml",
            "부동산": "http://www.fnnews.com/rss/r20/fn_realnews_realestate.xml",
            "산업": "http://www.fnnews.com/rss/r20/fn_realnews_industry.xml",
            "IT": "http://www.fnnews.com/rss/r20/fn_realnews_it.xml",
            "사설칼럼": "http://www.fnnews.com/rss/r20/fn_realnews_column.xml",
        }

        # User-Agent 목록
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
        ]

        self.articles = []

    def get_random_headers(self):
        """랜덤 User-Agent 헤더 반환"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
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

        # 여러 공백을 하나로 변환
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract_reporter_name(self, content):
        """기사 내용에서 기자명 추출"""
        if not content:
            return "기자명 없음"

        # 부산파이낸셜뉴스 기자명 패턴들
        patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*논설위원",
            r"([가-힣]{2,4})\s*편집위원",
            r"파이낸셜뉴스\s*([가-힣]{2,4})",
            r"FN\s*([가-힣]{2,4})",
            r"리포터\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*리포터",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
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
                        # 다른 형식 시도
                        dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        return date_str

    def get_article_content(self, url):
        """기사 본문 가져오기"""
        try:
            headers = self.get_random_headers()
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 부산파이낸셜뉴스 기사 본문 셀렉터들
            content_selectors = [
                "div.cont_view#article_content[itemprop='articleBody']",
                "div.article_content",
                "div.news_view_detail",
                "div.article_txt",
                "div.view_txt",
                ".news_cnt_detail_wrap",
                "div.news_text",
                "div.article-body",
                ".article_wrap .content",
                "div.story",
                ".detail_story",
                "div.article_view",
                ".view_cont",
            ]

            content = ""
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content = content_element.get_text()
                    break

            if not content:
                # 기본적인 p 태그에서 내용 추출
                paragraphs = soup.find_all("p")
                content = " ".join([p.get_text() for p in paragraphs])

            # 내용 정제
            content = self.clean_text(content)

            return content

        except Exception as e:
            self.logger.warning(f"기사 본문 추출 실패 ({url}): {e}")
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

            # 최대 20개 기사만 처리
            for i, item in enumerate(items[:1]):
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

                    # 기사 본문 가져오기
                    self.logger.info(f"기사 본문 추출 중: {title[:30]}...")
                    content = self.get_article_content(link)

                    # 기자명 추출: RSS author 우선 사용
                    author_elem = item.find("author")
                    if author_elem is not None and author_elem.text:
                        author_text = self.clean_text(author_elem.text)
                        match = re.search(r"([가-힣]{2,4})", author_text)
                        if match:
                            reporter = match.group(1) + " 기자"
                        else:
                            reporter = author_text
                    else:
                        reporter = self.extract_reporter_name(content)

                    article = {
                        "source": "파이낸셜뉴스",
                        "title": title,
                        "date": pub_date,
                        "category": category,
                        "reporter": reporter,
                        "content": content,
                    }

                    articles.append(article)

                    # 서버 부하 방지를 위한 딜레이
                    time.sleep(random.uniform(2, 5))

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
        self.logger.info("부산파이낸셜뉴스 RSS 크롤링 시작")

        # 주요 카테고리만 선별하여 크롤링 (전체기사 제외)
        main_categories = [
            "정치",
            "경제",
            "증권",
            "금융",
            "부동산",
            "산업",
            "IT",
            "사회",
            "국제",
            "연예",
            "스포츠",
            "문화",
        ]

        for category in main_categories:
            if category in self.rss_feeds:
                url = self.rss_feeds[category]
                self.logger.info(f"\n=== {category} 카테고리 크롤링 ===")

                articles = self.parse_rss_feed(category, url)
                self.articles.extend(articles)

                # 카테고리 간 딜레이
                time.sleep(random.uniform(3, 7))

        self.logger.info(f"\n총 {len(self.articles)}개 기사 수집 완료")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/파이낸셜뉴스_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["source", "title", "date", "category", "reporter", "content"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(self.articles)

            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            print(f"\n✅ 크롤링 완료! 결과 파일: {filename}")
            print(f"📊 총 수집된 기사: {len(self.articles)}개")

        except Exception as e:
            self.logger.error(f"CSV 파일 저장 실패: {e}")


def main():
    """메인 실행 함수"""
    crawler = BusanFinancialNewsCrawler()

    print("🚀 부산파이낸셜뉴스 RSS 크롤링을 시작합니다...")
    print("📰 수집 대상 카테고리: 정치, 경제, 증권, 금융, 부동산, 산업, IT, 사회, 국제, 연예, 스포츠, 문화")
    print("⏳ 서버 부하 방지를 위해 딜레이가 적용됩니다.\n")

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
