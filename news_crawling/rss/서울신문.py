import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
import time
import os
from urllib.parse import urljoin, urlparse
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SeoulShinmunCrawler:
    def __init__(self):
        self.base_url = "https://www.seoul.co.kr"
        self.sections = {
            "politics": {"url": "https://www.seoul.co.kr/newsList/politics/", "name": "정치"},
            "society": {"url": "https://www.seoul.co.kr/newsList/society/", "name": "사회"},
            "economy": {"url": "https://www.seoul.co.kr/newsList/economy/", "name": "경제"},
            "international": {"url": "https://www.seoul.co.kr/newsList/international/", "name": "국제"},
            "life": {"url": "https://www.seoul.co.kr/newsList/life/", "name": "생활"},
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def get_page_content(self, url, timeout=10):
        """웹페이지 내용을 가져오는 함수"""
        # 네트워크 오류 시 최대 3회 재시도
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, timeout=timeout)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except requests.RequestException as e:
                logger.warning(f"페이지 요청 실패({attempt+1}/3) ({url}): {e}")
                time.sleep(1)
        logger.error(f"페이지 요청 재시도 실패 ({url})")
        return None

    def extract_article_urls_from_section(self, section_url, max_pages=10):
        """섹션 페이지에서 기사 URL들을 추출(최대 max_pages)"""
        # 최대 max_pages페이지까지 순차적으로 기사 링크 수집
        article_urls = []
        for page in range(1, max_pages + 1):
            if page == 1:
                url = section_url
            else:
                url = f"{section_url}?page={page}"
            page_content = self.get_page_content(url)
            if not page_content:
                break
            soup = BeautifulSoup(page_content, "html.parser")
            list_wrap = soup.find("ul", class_="sectionContentWrap")
            if not list_wrap:
                break
            items = list_wrap.find_all("li", class_="newsBox_row1")
            if not items:
                break
            for li in items:
                a_tag = li.find("a", href=True)
                if a_tag:
                    full_url = urljoin(self.base_url, a_tag["href"])
                    if full_url not in article_urls:
                        article_urls.append(full_url)
        logger.info(f"추출된 기사 URL 수: {len(article_urls)}")
        return article_urls

    def extract_article_info(self, article_url, section_name):
        """개별 기사에서 상세 정보 추출"""
        content = self.get_page_content(article_url)
        if not content:
            return None

        try:
            soup = BeautifulSoup(content, "html.parser")

            # 제목 추출
            title = ""
            title_selectors = ["h1.title", "h1", ".article-title", ".news-title", "h2.title", "h2"]

            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title:
                        break

            # 텍스트에서 제목 추출 시도 (메타 태그)
            if not title:
                title_meta = soup.find("meta", {"property": "og:title"})
                if title_meta:
                    title = title_meta.get("content", "").strip()

            # 날짜 추출
            date = ""
            # URL에서 날짜 추출 시도
            date_match = re.search(r"id=(\d{8})", article_url)
            if date_match:
                date_str = date_match.group(1)
                try:
                    date_obj = datetime.strptime(date_str, "%Y%m%d")
                    date = date_obj.strftime("%Y-%m-%d")
                except:
                    pass

            # HTML에서 날짜 찾기
            if not date:
                date_patterns = [r"(\d{4}-\d{2}-\d{2})", r"(\d{4}\.\d{2}\.\d{2})", r"(\d{4}/\d{2}/\d{2})"]

                for pattern in date_patterns:
                    date_match = re.search(pattern, content)
                    if date_match:
                        date = date_match.group(1)
                        break

            # 기자명 추출
            author = ""
            author_patterns = [r"([가-힣]{2,4})\s*기자", r"기자\s*([가-힣]{2,4})", r"([가-힣]{2,4})\s*특파원"]

            for pattern in author_patterns:
                author_match = re.search(pattern, content)
                if author_match:
                    author = author_match.group(1)
                    break

            # 본문 추출
            article_text = ""
            # 본문 추출 우선: viewContent body18 color700
            view_elem = soup.select_one("div.viewContent.body18.color700")
            if view_elem:
                # 불필요한 태그 제거
                for tag in view_elem.find_all(["script", "style", "aside", "nav", "iframe", "figure"]):
                    tag.decompose()
                article_text = view_elem.get_text(separator=" ", strip=True)
            else:
                # 기존 본문 추출 로직
                article_text = ""
                article_selectors = [
                    "div.viewContent.body18.color700",
                    ".article-content",
                    ".news-content",
                    ".content",
                    "#article_txt",
                    ".article_txt",
                ]

                for selector in article_selectors:
                    article_elem = soup.select_one(selector)
                    if article_elem:
                        # 불필요한 태그 제거
                        for tag in article_elem.find_all(["script", "style", "aside", "nav"]):
                            tag.decompose()

                        article_text = article_elem.get_text().strip()
                        if article_text:
                            break

            # 본문이 없으면 전체 텍스트에서 추출
            if not article_text:
                # 스크립트, 스타일 태그 제거
                for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                article_text = soup.get_text()
                # 불필요한 공백 정리
                article_text = re.sub(r"\s+", " ", article_text).strip()

                # 너무 긴 텍스트는 적절히 자르기
                if len(article_text) > 5000:
                    article_text = article_text[:5000] + "..."

            return {
                "언론사명": "서울신문",
                "카테고리": section_name,
                "제목": title,
                "날짜": date,
                "기자명": author,
                "본문": article_text,
                "URL": article_url,
            }

        except Exception as e:
            logger.error(f"기사 정보 추출 실패 ({article_url}): {e}")
            return None

    def crawl_section(self, section_key, max_pages=10):
        """특정 섹션 크롤링"""
        if section_key not in self.sections:
            logger.error(f"알 수 없는 섹션: {section_key}")
            return []

        section = self.sections[section_key]
        section_name = section["name"]
        section_url = section["url"]

        logger.info(f"[{section_name}] 섹션 크롤링 시작")

        # 기사 URL들 추출
        article_urls = self.extract_article_urls_from_section(section_url, max_pages)

        if not article_urls:
            logger.warning(f"[{section_name}] 기사 URL을 찾을 수 없습니다.")
            return []

        articles = []

        for i, url in enumerate(article_urls, 1):
            logger.info(f"[{section_name}] 기사 {i}/{len(article_urls)} 처리 중...")

            article_info = self.extract_article_info(url, section_name)

            if article_info and article_info["제목"]:
                articles.append(article_info)
                logger.info(f"기사 추출 완료: {article_info['제목'][:50]}...")
            else:
                logger.warning(f"기사 정보 추출 실패: {url}")

            # 요청 간격 조절
            time.sleep(0.5)

        logger.info(f"[{section_name}] 섹션 크롤링 완료: {len(articles)}개 기사")
        return articles

    def crawl_all_sections(self, sections_to_crawl=None, max_articles_per_section=20):
        """모든 섹션 크롤링"""
        if sections_to_crawl is None:
            sections_to_crawl = list(self.sections.keys())

        logger.info(f"크롤링 대상 섹션: {', '.join([self.sections[s]['name'] for s in sections_to_crawl])}")

        all_articles = []
        section_results = {}

        for section_key in sections_to_crawl:
            try:
                articles = self.crawl_section(section_key, max_articles_per_section)
                all_articles.extend(articles)
                section_results[self.sections[section_key]["name"]] = len(articles)

                # 섹션 간 간격
                time.sleep(1)

            except Exception as e:
                logger.error(f"[{self.sections[section_key]['name']}] 섹션 크롤링 오류: {e}")
                section_results[self.sections[section_key]["name"]] = 0

        return all_articles, section_results

    def save_to_csv(self, articles, filename=None, split_by_section=False):
        """데이터를 CSV 파일로 저장"""
        if not articles:
            logger.warning("저장할 데이터가 없습니다.")
            return []

        df = pd.DataFrame(articles)

        # 열 순서 정리 (URL 제외)
        column_order = ["언론사명", "제목", "날짜", "카테고리", "기자명", "본문"]
        df = df.reindex(columns=column_order)

        # results 디렉토리 생성
        os.makedirs("results", exist_ok=True)

        saved_files = []

        if split_by_section:
            # 섹션별로 파일 저장
            for category in df["카테고리"].unique():
                section_df = df[df["카테고리"] == category]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                section_filename = f"results/서울신문_{category}_{timestamp}.csv"

                section_df.to_csv(section_filename, index=False, encoding="utf-8-sig")

                logger.info(f"✓ [서울신문 {category}] CSV 파일 저장: {section_filename}")
                logger.info(f"  - {len(section_df)}개 기사, {os.path.getsize(section_filename):,} bytes")
                saved_files.append(section_filename)
        else:
            # 통합 파일로 저장
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"results/서울신문_전체_{timestamp}.csv"

            df.to_csv(filename, index=False, encoding="utf-8-sig")

            logger.info(f"✓ 서울신문 통합 CSV 파일 저장: {filename}")
            logger.info(f"  - 총 {len(df)}개 기사, {os.path.getsize(filename):,} bytes")
            saved_files.append(filename)

        return saved_files

    def setup_chrome_driver(self, headless=True):
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("서울신문 크롤링 프로그램")
    print("=" * 60)

    crawler = SeoulShinmunCrawler()

    print("\n사용 가능한 섹션:")
    for key, info in crawler.sections.items():
        print(f"  - {key}: {info['name']}")

    # 사용자 설정
    sections_to_crawl = None  # 모든 섹션 (특정 섹션: ['politics', 'society'])
    max_articles_per_section = 20  # 각 섹션당 최대 기사 수
    split_by_section = False  # True: 섹션별 파일, False: 통합 파일

    try:
        # 크롤링 실행
        articles, section_results = crawler.crawl_all_sections(sections_to_crawl, max_articles_per_section)

        if articles:
            # CSV 파일로 저장
            saved_files = crawler.save_to_csv(articles, split_by_section=split_by_section)

            # 결과 요약
            print("\n" + "=" * 60)
            print("서울신문 크롤링 완료 결과")
            print("=" * 60)
            print(f"✓ 총 수집 기사 수: {len(articles):,}개")

            print(f"\n📊 섹션별 수집 결과:")
            for section, count in section_results.items():
                print(f"  - {section}: {count:,}개")

            print(f"\n📁 저장된 파일:")
            for file in saved_files:
                print(f"  - {file}")

            # 샘플 데이터 표시
            df = pd.DataFrame(articles)
            print(f"\n📋 카테고리별 분포:")
            category_counts = df["카테고리"].value_counts()
            for category, count in category_counts.items():
                print(f"  - {category}: {count}개")

            print(f"\n📰 수집된 기사 샘플 (최대 3개):")
            for i in range(min(3, len(df))):
                row = df.iloc[i]
                print(f"{i+1}. [서울신문 {row['카테고리']}] {row['제목']}")
                print(f"   기자: {row['기자명']}, 날짜: {row['날짜']}")
                print()

            return saved_files
        else:
            print("❌ 크롤링된 기사가 없습니다.")
            return None

    except Exception as e:
        logger.error(f"❌ 프로그램 실행 중 오류 발생: {e}")
        return None


def crawl_specific_sections(section_list, max_articles=10):
    """특정 섹션들만 크롤링하는 편의 함수"""
    crawler = SeoulShinmunCrawler()
    articles, section_results = crawler.crawl_all_sections(section_list, max_articles)

    if articles:
        saved_files = crawler.save_to_csv(articles, split_by_section=True)
        print(f"\n✅ 서울신문 크롤링 완료: {len(articles)}개 기사 수집")
        return saved_files
    else:
        print("❌ 서울신문 크롤링 실패")
        return None


if __name__ == "__main__":
    # 메인 프로그램 실행
    result_files = main()
