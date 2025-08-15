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
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TongilNewsRSSCrawler:
    def __init__(self):
        self.base_url = "https://www.tongilnews.com"
        self.session = requests.Session()

        # 다양한 User-Agent 설정
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]

        # 통일뉴스 RSS 피드 목록
        self.rss_feeds = {
            "전체기사": "https://www.tongilnews.com/rss/allArticle.xml",
            "현장소식": "https://www.tongilnews.com/rss/S1N1.xml",
            "북한소식": "https://www.tongilnews.com/rss/S1N2.xml",
            "정부정책": "https://www.tongilnews.com/rss/S1N6.xml",
            "오피니언": "https://www.tongilnews.com/rss/S1N9.xml",
            "특집연재": "https://www.tongilnews.com/rss/S1N11.xml",
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

    def parse_rss_feed(self, rss_url):
        """RSS 피드 파싱"""
        logger.info(f"RSS 피드 파싱 중: {rss_url}")

        response = self.safe_request(rss_url)
        if not response:
            return []

        try:
            # UTF-8로 디코딩
            content = response.content.decode("utf-8")
            root = ET.fromstring(content)

            articles = []
            items = root.findall(".//item")

            for item in items:
                try:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pubdate_elem = item.find("pubDate")
                    description_elem = item.find("description")

                    if title_elem is not None and link_elem is not None:
                        title = title_elem.text.strip() if title_elem.text else ""
                        link = link_elem.text.strip() if link_elem.text else ""
                        pubdate = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""
                        description = (
                            description_elem.text.strip()
                            if description_elem is not None and description_elem.text
                            else ""
                        )
                        # RSS author 태그에서 기자명 추출 (우선)
                        author_elem = item.find("author")
                        if author_elem is not None and author_elem.text:
                            author_text = author_elem.text.strip()
                            # 한글 이름 부분만 추출
                            m = re.search(r"([가-힣]{2,4})", author_text)
                            reporter = m.group(1) if m else author_text
                        else:
                            # description에서 기자명 추출
                            reporter = self.extract_reporter_from_description(description)

                        articles.append(
                            {
                                "title": title,
                                "link": link,
                                "pubdate": pubdate,
                                "description": description,
                                "reporter": reporter,
                            }
                        )

                except Exception as e:
                    logger.warning(f"RSS 아이템 파싱 오류: {str(e)}")
                    continue

            logger.info(f"RSS에서 {len(articles)}개 기사 발견")
            return articles

        except ET.ParseError as e:
            logger.error(f"RSS XML 파싱 오류: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"RSS 파싱 중 오류: {str(e)}")
            return []

    def extract_reporter_from_description(self, description):
        """description에서 기자명 추출"""
        if not description:
            return ""

        # 통일뉴스 특화 기자명 패턴들
        patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"([가-힣]{2,4})\s*통신원",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*대표",
            r"([가-힣]{2,4})\s*원장",
            r"([가-힣]{2,4})\s*교수",
            r"([가-힣]{2,4})\s*연구위원",
            r"\/\s*([가-힣]{2,4})",  # "/ 김철수" 형태
            r"([가-힣]{2,4})\s*\/",  # "김철수 /" 형태
        ]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()

        return ""

    def extract_article_content(self, article_url):
        """기사 본문 및 기자명 추출 - 수정된 버전"""
        logger.info(f"기사 내용 추출 중: {article_url}")

        response = self.safe_request(article_url)
        if not response:
            return "", ""

        try:
            # 응답 인코딩 설정
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            # 원문 페이지의 article-view-content-div에서 본문 및 기자명 우선 추출
            article_div = soup.find("article", id="article-view-content-div") or soup.find(
                "div", id="article-view-content-div"
            )
            if article_div:
                paragraphs = article_div.find_all("p")
                texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                if texts:
                    # 기자명 추출: view-editors strong 안
                    editor_elem = article_div.select_one(".view-editors strong")
                    if editor_elem:
                        reporter = editor_elem.get_text(strip=True).replace(" 기자", "")
                    else:
                        m = re.search(r"([가-힣]{2,4})\s*(?:기자|통신원|특파원)", texts[-1])
                        reporter = m.group(1) if m else ""
                    # 본문 합치기
                    content = " ".join(texts)
                    content = re.sub(r"\s+", " ", content).strip()
                    logger.info(f"원문 본문 추출 완료, 기자: {reporter}")
                    return content, reporter

            # 기사 본문 추출 - 통일뉴스 전용 선택자들
            content = ""

            # 통일뉴스의 실제 본문 선택자들 (우선순위 순)
            content_selectors = [
                "#article-view-content-div",  # 메인 본문 컨테이너
                ".article-content",
                ".view-content",
                "#articleText",
                ".content",
                'div[itemprop="articleBody"]',
                ".article_view",
            ]

            article_content = None
            for selector in content_selectors:
                article_content = soup.select_one(selector)
                if article_content:
                    logger.info(f"본문을 찾았습니다: {selector}")
                    break

            # 본문을 찾지 못한 경우, 더 넓은 범위에서 찾기
            if not article_content:
                # 제목 다음 영역을 찾아서 본문 추출
                title_elem = soup.find("h1") or soup.find("h2") or soup.find(".title")
                if title_elem:
                    # 제목 이후의 모든 p 태그들을 본문으로 간주
                    paragraphs = soup.find_all("p")
                    if paragraphs:
                        content_parts = []
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
                # 본문 컨테이너를 찾은 경우
                # 불필요한 태그 제거
                for tag in article_content.find_all(["script", "style", "iframe", "embed", "noscript"]):
                    tag.decompose()

                # 이미지 캡션 제거
                for tag in article_content.find_all(["figcaption", ".caption", ".photo-caption"]):
                    tag.decompose()

                # 광고 관련 요소 제거
                for tag in article_content.find_all(["div"], class_=re.compile("ad|banner|광고")):
                    tag.decompose()

                # 텍스트 추출
                content = article_content.get_text(separator=" ", strip=True)

            # 텍스트 정리
            if content:
                content = re.sub(r"\s+", " ", content)
                content = content.replace("\n", " ").replace("\r", " ")
                # 너무 짧은 경우 (헤더/푸터만 추출된 경우) 제외
                if len(content) < 100:
                    content = ""

            # 기자명 추출
            reporter = ""

            # 1. 기자명 전용 요소에서 추출
            reporter_selectors = [".writer", ".reporter", ".byline", ".author", ".article-author", ".news-author"]

            for selector in reporter_selectors:
                reporter_elem = soup.select_one(selector)
                if reporter_elem:
                    reporter_text = reporter_elem.get_text(strip=True)
                    match = re.search(r"([가-힣]{2,4})\s*(?:기자|통신원|특파원)", reporter_text)
                    if match:
                        reporter = match.group(1)
                        break

            # 2. 본문에서 기자명 추출 시도
            if not reporter and content:
                # 본문 첫 부분에서 기자명 찾기
                first_100_chars = content[:100]
                match = re.search(r"([가-힣]{2,4})\s*(?:기자|통신원|특파원)", first_100_chars)
                if match:
                    reporter = match.group(1)

                # 본문 끝 부분에서 기자명 찾기
                if not reporter:
                    last_100_chars = content[-100:]
                    match = re.search(r"([가-힣]{2,4})\s*(?:기자|통신원|특파원)", last_100_chars)
                    if match:
                        reporter = match.group(1)

            # 3. 전체 페이지에서 기자명 찾기
            if not reporter:
                page_text = soup.get_text()
                match = re.search(r"([가-힣]{2,4})\s*(?:기자|통신원|특파원)", page_text)
                if match:
                    reporter = match.group(1)

            logger.info(f"본문 추출 완료: {len(content)}자, 기자: {reporter}")
            return content, reporter

        except Exception as e:
            logger.error(f"기사 내용 추출 오류: {str(e)}")
            return "", ""

    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return ""

        try:
            # RSS 날짜 형식: "Fri, 02 Aug 2025 20:44:49 +0900"
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

                crawled_article = {
                    "category": category_name,
                    "title": article["title"],
                    "date": self.parse_date(article["pubdate"]),
                    "reporter": final_reporter,
                    "content": content,
                    "url": article["link"],
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
                fieldnames = ["category", "title", "date", "reporter", "content", "url"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in articles:
                    writer.writerow(article)

            logger.info(f"CSV 저장 완료: {filename} ({len(articles)}개 기사)")

        except Exception as e:
            logger.error(f"CSV 저장 오류: {str(e)}")

    def crawl_all_categories(self, max_articles_per_category=None):
        """모든 카테고리 크롤링"""
        logger.info("=== 통일뉴스 전체 카테고리 크롤링 시작 ===")

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
        return all_articles


def main():
    """메인 실행 함수: 모든 카테고리를 각각 20개씩 수집해 단일 CSV에 저장"""
    crawler = TongilNewsRSSCrawler()
    # 결과 디렉토리 생성
    os.makedirs("results", exist_ok=True)
    # 전체 카테고리 수집 (카테고리별 최대 20개)
    articles = crawler.crawl_all_categories(max_articles_per_category=20)
    # 파일명 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/통일뉴스_전체_{timestamp}.csv"
    # CSV 저장
    with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for art in articles:
            writer.writerow(
                {
                    "언론사": "통일뉴스",
                    "제목": art["title"],
                    "날짜": art["date"],
                    "카테고리": art["category"],
                    "기자명": art["reporter"] or "미상",
                    "본문": art["content"],
                }
            )
    print(f"\n총 {len(articles)}개 기사 저장 완료: {filename}")


if __name__ == "__main__":
    main()
