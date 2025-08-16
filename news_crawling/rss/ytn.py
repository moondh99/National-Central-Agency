import os
import csv
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class YTNScraper:
    def __init__(self, headless=False):
        """YTN 스크래퍼 초기화"""
        self.sections = {
            "0101": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0101", "name": "정치"},
            "0102": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0102", "name": "경제"},
            "0103": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0103", "name": "사회"},
            "0115": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0115", "name": "생활/문화"},
            "0104": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0104", "name": "국제"},
            "0106": {"url": "https://www.ytn.co.kr/news/list.php?mcd=0106", "name": "IT/과학"},
        }

        self.articles_data = []

        # Chrome 옵션 설정
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 드라이버 초기화
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

        # 결과 저장 디렉토리 생성
        if not os.path.exists("results"):
            os.makedirs("results")

    def click_more_button(self, max_clicks=10):
        """더보기 버튼 클릭하여 추가 기사 로드"""
        click_count = 0

        while click_count < max_clicks:
            try:
                # 더보기 버튼 찾기
                more_button = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn_white_arr_down")))

                # 버튼이 보이는지 확인
                if not more_button.is_displayed():
                    logger.info("  더 이상 로드할 기사가 없습니다.")
                    break

                # JavaScript로 클릭 실행
                self.driver.execute_script("arguments[0].scrollIntoView(true);", more_button)
                time.sleep(1)

                # onclick 속성에서 함수 호출 추출하여 실행
                onclick_attr = more_button.get_attribute("href")
                if "moreNews" in onclick_attr:
                    self.driver.execute_script(onclick_attr.replace("javascript:", ""))
                else:
                    self.driver.execute_script("arguments[0].click();", more_button)

                click_count += 1
                logger.info(f"  더보기 버튼 클릭 {click_count}회")

                # 새 콘텐츠 로딩 대기
                time.sleep(3)

            except TimeoutException:
                logger.info("  더보기 버튼을 찾을 수 없습니다.")
                break
            except Exception as e:
                logger.error(f"  더보기 버튼 클릭 중 오류: {e}")
                break

        return click_count

    def extract_article_list(self):
        """기사 목록 추출"""
        articles = []

        try:
            # 기사 목록 컨테이너 찾기
            news_items = self.driver.find_elements(By.CSS_SELECTOR, "div.news_list")

            for item in news_items:
                try:
                    article_info = {}

                    # 제목과 링크
                    title_elem = item.find_element(By.CSS_SELECTOR, "div.title a")
                    article_info["title"] = title_elem.text.strip()
                    article_info["url"] = title_elem.get_attribute("href")

                    # URL이 없거나 잘못된 경우 스킵
                    if not article_info["url"] or "javascript" in article_info["url"]:
                        continue

                    # 날짜/시간
                    try:
                        date_elem = item.find_element(By.CSS_SELECTOR, "div.date")
                        article_info["date"] = date_elem.text.strip()
                    except:
                        article_info["date"] = ""

                    # 요약 (숨겨진 content div)
                    try:
                        content_elem = item.find_element(By.CSS_SELECTOR, "div.content")
                        article_info["summary"] = content_elem.text.strip()
                    except:
                        article_info["summary"] = ""

                    # 썸네일 이미지 URL (선택사항)
                    try:
                        img_elem = item.find_element(By.CSS_SELECTOR, "div.photo img")
                        article_info["thumbnail"] = img_elem.get_attribute("src")
                    except:
                        article_info["thumbnail"] = ""

                    articles.append(article_info)

                except Exception as e:
                    logger.error(f"  기사 정보 추출 중 오류: {e}")
                    continue

            logger.info(f"  총 {len(articles)}개의 기사 목록 추출 완료")
            return articles

        except Exception as e:
            logger.error(f"  기사 목록 추출 중 오류: {e}")
            return articles

    def extract_article_content(self, url):
        """개별 기사 본문 추출"""
        try:
            # 새 탭에서 기사 열기
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.get(url)

            # 본문 로딩 대기
            time.sleep(2)

            content = ""
            reporter = ""
            category = ""

            try:
                # 카테고리 추출 (breadcrumb에서)
                breadcrumb = self.driver.find_elements(By.CSS_SELECTOR, "div.breadcrumb a, nav.breadcrumb a")
                if len(breadcrumb) > 1:
                    category = breadcrumb[1].text.strip()
            except:
                category = ""

            try:
                # 본문 추출 - 여러 가능한 선택자 시도
                content_selectors = [
                    "div.paragraph",
                    "div.news_content",
                    "div.article_paragraph",
                    "span[style*='display:inline-block']",
                    "div#CmAdContent",
                ]

                content_found = False
                for selector in content_selectors:
                    try:
                        content_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if content_elem and content_elem.text.strip():
                            raw_content = content_elem.text.strip()

                            # 본문 클리닝
                            content = self.clean_article_content(raw_content)
                            content_found = True
                            break
                    except:
                        continue

                # 본문을 찾지 못한 경우 대체 방법
                if not content_found:
                    # 본문이 포함된 span 태그 찾기
                    spans = self.driver.find_elements(By.TAG_NAME, "span")
                    for span in spans:
                        style = span.get_attribute("style")
                        if style and "display:inline-block" in style and "word-break:keep-all" in style:
                            raw_content = span.text.strip()
                            if len(raw_content) > 100:  # 충분한 길이의 텍스트만
                                content = self.clean_article_content(raw_content)
                                break

            except Exception as e:
                logger.error(f"  본문 추출 실패: {e}")
                content = ""

            try:
                # 기자 정보 추출
                reporter_patterns = [
                    r"YTN\s+([가-힣]+)\s*\(",
                    r"기자\s*:\s*([가-힣]+)",
                    r"([가-힣]+)\s+기자",
                    r"([가-힣]+)\s*\([\w@]+\.[\w]+\)",
                ]

                for pattern in reporter_patterns:
                    match = re.search(pattern, content)
                    if match:
                        reporter = match.group(1).strip()
                        break

                # 메타 정보에서도 기자명 찾기
                if not reporter:
                    try:
                        meta_reporter = self.driver.find_element(By.CSS_SELECTOR, "meta[name='author']")
                        reporter = meta_reporter.get_attribute("content")
                    except:
                        pass

            except:
                reporter = ""

            # 탭 닫기
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            return content, category, reporter

        except Exception as e:
            logger.error(f"  기사 내용 추출 중 오류: {e}")
            # 오류 발생 시 메인 탭으로 돌아가기
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return "", "", ""

    def clean_article_content(self, content):
        """기사 본문 클리닝"""
        # 광고 관련 텍스트 제거
        remove_patterns = [
            r"<iframe.*?</iframe>",
            r"\[카카오톡\].*?YTN.*?검색.*?채널.*?추가",
            r"\[전화\].*?\d{2,3}-\d{3,4}-\d{4}",
            r"\[메일\].*?@ytn\.co\.kr",
            r"※.*?당신의 제보가 뉴스가 됩니다.*?",
            r"▶.*?네이버.*?구독.*?",
            r"▶.*?카카오톡.*?친구.*?",
            r"Copyright.*?무단.*?전재.*?재배포.*?금지",
            r"<br\s*/?>",
            r"<.*?>",  # 모든 HTML 태그 제거
        ]

        cleaned_content = content
        for pattern in remove_patterns:
            cleaned_content = re.sub(pattern, " ", cleaned_content, flags=re.IGNORECASE | re.DOTALL)

        # 연속된 공백 제거
        cleaned_content = re.sub(r"\s+", " ", cleaned_content)

        # 앞뒤 공백 제거
        cleaned_content = cleaned_content.strip()

        return cleaned_content

    def scrape_section(self, section_code, section_info, max_articles=30, load_more_clicks=3):
        """특정 섹션 스크래핑"""
        section_name = section_info["name"]
        section_url = section_info["url"]

        logger.info(f"\n{'='*50}")
        logger.info(f"섹션 스크래핑 시작: {section_name} ({section_url})")
        logger.info(f"{'='*50}")

        try:
            # 페이지 로드
            self.driver.get(section_url)
            time.sleep(3)

            # 더보기 버튼 클릭하여 추가 기사 로드
            self.click_more_button(load_more_clicks)

            # 기사 목록 추출
            articles = self.extract_article_list()

            # 중복 제거
            seen_urls = set()
            unique_articles = []
            for article in articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    unique_articles.append(article)

            # 지정된 수만큼만 처리
            articles_to_process = unique_articles[:max_articles]

            logger.info(f"{len(articles_to_process)}개 기사 상세 정보 수집 시작")

            section_articles = []
            for idx, article in enumerate(articles_to_process, 1):
                logger.info(f"  [{idx}/{len(articles_to_process)}] {article['title'][:30]}...")

                # 본문, 카테고리, 기자 정보 추출
                content, category, reporter = self.extract_article_content(article["url"])

                # 카테고리가 비어있으면 섹션 이름 사용
                if not category:
                    category = section_name

                # 데이터 저장
                # 필요 컬럼만 보존: 언론사, 제목, 날짜, 카테고리, 기자명, 본문
                article_data = {
                    "언론사": "YTN",
                    "제목": article["title"],
                    "날짜": article.get("date", ""),
                    "카테고리": category,
                    "기자명": reporter,
                    "본문": content,
                }

                section_articles.append(article_data)
                self.articles_data.append(article_data)

                # 서버 부하 방지를 위한 대기
                time.sleep(1)

            logger.info(f"섹션 '{section_name}' 스크래핑 완료: {len(section_articles)}개 기사 수집")
            return section_articles

        except Exception as e:
            logger.error(f"섹션 '{section_name}' 스크래핑 중 오류 발생: {e}")
            return []

    def scrape_all_sections(self, sections_to_scrape=None, max_articles_per_section=30, load_more_clicks=3):
        """모든 섹션 또는 지정된 섹션들 스크래핑"""
        # 스크래핑할 섹션 결정
        if sections_to_scrape is None:
            sections_to_scrape = list(self.sections.keys())

        logger.info(f"\n{'#'*60}")
        logger.info(f"YTN 멀티 섹션 스크래핑 시작")
        logger.info(
            f"대상 섹션: {', '.join([self.sections[s]['name'] for s in sections_to_scrape if s in self.sections])}"
        )
        logger.info(f"섹션당 최대 기사 수: {max_articles_per_section}")
        logger.info(f"{'#'*60}")

        start_time = datetime.now()

        for section_code in sections_to_scrape:
            if section_code in self.sections:
                self.scrape_section(
                    section_code, self.sections[section_code], max_articles_per_section, load_more_clicks
                )
                # 섹션 간 대기 시간
                time.sleep(2)
            else:
                logger.warning(f"알 수 없는 섹션 코드: {section_code}")

        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        logger.info(f"\n{'#'*60}")
        logger.info(f"전체 스크래핑 완료")
        logger.info(f"총 수집 기사 수: {len(self.articles_data)}개")
        logger.info(f"소요 시간: {elapsed_time:.2f}초")
        logger.info(f"{'#'*60}")

    def save_to_csv(self):
        """수집한 데이터를 CSV 파일로 저장"""
        if not self.articles_data:
            logger.warning("저장할 데이터가 없습니다.")
            return None

        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results/YTN_전체_{timestamp}.csv"

        # CSV 저장
        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            # 언론사, 제목, 날짜, 카테고리, 기자명, 본문 순으로 CSV 저장
            fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(self.articles_data)

        logger.info(f"데이터 저장 완료: {filename}")
        logger.info(f"저장된 기사 수: {len(self.articles_data)}개")

        # 섹션별 통계 출력
        section_stats = {}
        for article in self.articles_data:
            section = article.get("섹션", "기타")
            section_stats[section] = section_stats.get(section, 0) + 1

        logger.info("\n섹션별 수집 통계:")
        for section, count in section_stats.items():
            logger.info(f"  - {section}: {count}개")

        return filename

    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("드라이버 종료")


def main():
    """메인 실행 함수"""
    scraper = None
    try:
        # 스크래퍼 초기화 (headless=True로 설정하면 브라우저 창 없이 실행)
        scraper = YTNScraper(headless=True)

        # 옵션 1: 모든 섹션 스크래핑
        scraper.scrape_all_sections(
            max_articles_per_section=50, load_more_clicks=5  # 각 섹션당 20개 기사  # 더보기 버튼 2회 클릭
        )

        # CSV 파일 저장
        scraper.save_to_csv()

    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"실행 중 오류: {e}")
    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    main()
