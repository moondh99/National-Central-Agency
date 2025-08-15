import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import csv
import time
import random
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SisaJournalRSSCrawler:
    def __init__(self):
        self.base_url = "https://www.sisajournal.com"
        self.session = requests.Session()

        # 다양한 User-Agent 설정
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]

        # 시사저널 RSS 피드 목록
        self.rss_feeds = {
            "전체기사": "https://www.sisajournal.com/rss/allArticle.xml",
            "사회": "https://www.sisajournal.com/rss/S1N47.xml",
            "네트워크": "https://www.sisajournal.com/rss/S1N53.xml",
            "경제": "https://www.sisajournal.com/rss/S1N54.xml",
            "정치": "https://www.sisajournal.com/rss/S1N58.xml",
            "국제": "https://www.sisajournal.com/rss/S1N59.xml",
        }

        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        # 크롤러 언론사명 설정
        self.media_name = "시사저널"

    def get_random_user_agent(self):
        return random.choice(self.user_agents)

    def safe_request(self, url, max_retries=3):
        """안전한 요청 처리"""
        for attempt in range(max_retries):
            try:
                self.session.headers["User-Agent"] = self.get_random_user_agent()
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"요청 실패 (시도 {attempt + 1}/{max_retries}): {url} - {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                else:
                    logger.error(f"최대 재시도 초과: {url}")
                    return None

    # removed internal main method - using top-level auto-run logic

    def extract_article_content(self, article_url):
        """기사 본문 및 기자명 추출 - 시사저널 특화"""
        logger.info(f"기사 내용 추출 중: {article_url}")

        response = self.safe_request(article_url)
        if not response:
            return "", ""

        try:
            # 응답 인코딩 설정
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            # 기사 본문 추출: 원문 페이지의 <article id="article-view-content-div"> 우선 사용
            content = ""
            content_selectors = [
                "article#article-view-content-div[itemprop='articleBody']",  # 원문 본문 컨테이너
                "#article-view-content-div",  # ID 기반 컨테이너
                ".article-content",
                ".view-content",
                "#articleText",
                ".news-content",
                ".content",
                "div[itemprop='articleBody']",
                ".article_view",
                ".article-body",
            ]

            article_content = None
            for selector in content_selectors:
                article_content = soup.select_one(selector)
                if article_content:
                    logger.info(f"본문을 찾았습니다: {selector}")
                    break

            # 본문을 찾지 못한 경우, 더 넓은 범위에서 찾기
            if not article_content:
                # 기사 제목을 찾아서 그 이후의 모든 텍스트를 본문으로 간주
                title_selectors = ["h1.article-title", "h1.title", "h1", "h2", ".title"]

                title_elem = None
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        break

                if title_elem:
                    # 제목 이후의 모든 p 태그들을 본문으로 간주
                    next_elem = title_elem.find_next_sibling()
                    content_parts = []

                    # 제목 다음 요소부터 순회하며 본문 수집
                    current = title_elem.parent
                    paragraphs = current.find_all("p")

                    for p in paragraphs:
                        p_text = p.get_text(strip=True)
                        if p_text and len(p_text) > 20:  # 의미있는 길이의 텍스트만
                            content_parts.append(p_text)

                    content = " ".join(content_parts)

                # 여전히 본문이 없으면 전체 텍스트에서 추출
                if not content:
                    all_text = soup.get_text()
                    # 제목을 찾아서 그 이후 텍스트를 본문으로 사용
                    title_text = soup.find("h1")
                    if title_text:
                        title_text = title_text.get_text(strip=True)
                        if title_text in all_text:
                            content_start = all_text.find(title_text) + len(title_text)
                            content = all_text[content_start:].strip()
            else:
                # 본문 컨테이너를 찾은 경우: p 태그에서만 텍스트 추출
                # 이미지, 광고, 기타 요소 제거
                for tag in article_content.find_all(["script", "style", "iframe", "embed", "noscript", "figure"]):
                    tag.decompose()
                # 단락별 본문 수집
                paras = article_content.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))

            # 텍스트 정리
            if content:
                content = re.sub(r"\s+", " ", content)
                content = content.replace("\n", " ").replace("\r", " ")
                # 너무 짧은 경우 (헤더/푸터만 추출된 경우) 제외
                if len(content) < 100:
                    content = ""

            # 본문 추출 완료 - RSS feed의 author 태그 사용
            logger.info(f"본문 추출 완료: {len(content)}자")
            return content, ""

        except Exception as e:
            logger.error(f"기사 내용 추출 오류: {str(e)}")
            return "", ""

    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return ""

        try:
            # RSS 날짜 형식 파싱
            if "," in date_str:
                date_part = date_str.split(",", 1)[1].strip()
                # "+0900" 제거
                if "+" in date_part:
                    date_part = date_part.split("+")[0].strip()
                elif "-" in date_part and date_part.count("-") > 2:
                    date_part = date_part.rsplit("-", 1)[0].strip()

                # 날짜 파싱 시도
                try:
                    parsed_date = datetime.strptime(date_part, "%d %b %Y %H:%M:%S")
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            # 다른 형식들 시도
            formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M:%S"]

            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str.strip(), fmt)
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

            return date_str.strip()

        except Exception as e:
            logger.warning(f"날짜 파싱 오류: {date_str} - {str(e)}")
            return date_str

    def crawl_category(self, category_name, rss_url, max_articles=None):
        """특정 카테고리 크롤링"""
        logger.info(f"=== {category_name} 카테고리 크롤링 시작 ===")

        # RSS 피드에서 기사 목록 가져오기
        articles = self.parse_rss_feed(rss_url)

        if max_articles:
            articles = articles[:max_articles]

        crawled_articles = []

        for i, article in enumerate(articles, 1):
            logger.info(f"기사 {i}/{len(articles)} 처리 중: {article['title'][:50]}...")

            try:
                # 기사 본문 추출
                content, page_reporter = self.extract_article_content(article["link"])

                # 기자명 결정 (페이지 > RSS description)
                final_reporter = page_reporter if page_reporter else article["reporter"]

                # 기사 정보에 언론사 추가 및 필드 순서 변경
                crawled_article = {
                    "media": self.media_name,
                    "title": article["title"],
                    "date": self.parse_date(article["pubdate"]),
                    "category": category_name,
                    "reporter": final_reporter,
                    "content": content,
                }

                crawled_articles.append(crawled_article)

                # 서버 부하 방지를 위한 딜레이
                time.sleep(random.uniform(1, 3))

            except Exception as e:
                logger.error(f"기사 처리 오류: {article['link']} - {str(e)}")
                continue

        logger.info(f"=== {category_name} 카테고리 완료: {len(crawled_articles)}개 기사 ===")
        return crawled_articles

    def save_to_csv(self, articles, filename):
        """CSV 파일로 저장"""
        if not articles:
            logger.warning("저장할 기사가 없습니다.")
            return

        logger.info(f"CSV 파일 저장 중: {filename}")

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                # 저장할 CSV 컬럼 순서: 언론사, 제목, 날짜, 카테고리, 기자명, 본문
                fieldnames = ["media", "title", "date", "category", "reporter", "content"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in articles:
                    writer.writerow(article)

            logger.info(f"CSV 저장 완료: {filename} ({len(articles)}개 기사)")

        except Exception as e:
            logger.error(f"CSV 저장 오류: {str(e)}")

    def crawl_all_categories(self, max_articles_per_category=None):
        """모든 카테고리 크롤링"""
        logger.info("=== 시사저널 전체 카테고리 크롤링 시작 ===")

        all_articles = []

        for category_name, rss_url in self.rss_feeds.items():
            try:
                category_articles = self.crawl_category(category_name, rss_url, max_articles_per_category)
                all_articles.extend(category_articles)

                # 카테고리 간 딜레이
                time.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"{category_name} 카테고리 크롤링 오류: {str(e)}")
                continue

        logger.info(f"=== 전체 크롤링 완료: {len(all_articles)}개 기사 ===")
        return all_articles

    def crawl_specific_categories(self, categories, max_articles_per_category=None):
        """특정 카테고리들만 크롤링"""
        logger.info(f"=== 선택된 카테고리 크롤링 시작: {categories} ===")

        all_articles = []

        for category_name in categories:
            if category_name in self.rss_feeds:
                try:
                    rss_url = self.rss_feeds[category_name]
                    category_articles = self.crawl_category(category_name, rss_url, max_articles_per_category)
                    all_articles.extend(category_articles)

                    # 카테고리 간 딜레이
                    time.sleep(random.uniform(2, 5))

                except Exception as e:
                    logger.error(f"{category_name} 카테고리 크롤링 오류: {str(e)}")
                    continue
            else:
                logger.warning(f"존재하지 않는 카테고리: {category_name}")

        logger.info(f"=== 선택된 카테고리 크롤링 완료: {len(all_articles)}개 기사 ===")

    def parse_rss_feed(self, rss_url):
        """RSS 피드 파싱 - author 포함"""
        response = self.safe_request(rss_url)
        if not response:
            return []
        try:
            xml_content = response.text
            root = ET.fromstring(xml_content)
            items = []
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                link_elem = item.find("link")
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                pubdate_elem = item.find("pubDate")
                pubdate = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""
                # author 추출
                author = ""
                author_elem = item.find("author")
                if author_elem is None:
                    author_elem = item.find(".//{http://purl.org/dc/elements/1.1/}creator")
                if author_elem is not None and author_elem.text:
                    author_text = author_elem.text.strip()
                    # 기자명 패턴 매칭
                    match = re.search(r"([가-힣]{2,4})\s*기자", author_text)
                    if match:
                        author = match.group(1)
                    else:
                        m2 = re.search(r"([가-힣]+)", author_text)
                        author = m2.group(1) if m2 else author_text
                items.append({"title": title, "link": link, "pubdate": pubdate, "reporter": author})
            return items
        except Exception as e:
            logger.error(f"RSS 파싱 오류: {e}")
            return []


if __name__ == "__main__":
    crawler = SisaJournalRSSCrawler()
    print("시사저널 RSS 크롤러 자동 실행: 모든 카테고리에서 20개씩 수집합니다.")
    all_articles = []
    for category, rss_url in crawler.rss_feeds.items():
        print(f"{category} 카테고리 크롤링 시작...")
        articles = crawler.crawl_category(category, rss_url, max_articles=20)
        all_articles.extend(articles)
        time.sleep(random.uniform(1, 2))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 파일명에 언론사명 포함
    filename = f"results/{crawler.media_name}_전체_{timestamp}.csv"
    crawler.save_to_csv(all_articles, filename)
    print(f"크롤링 완료! 저장된 파일: {filename}, 총 기사 수: {len(all_articles)}")
