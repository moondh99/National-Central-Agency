import os
import csv
import time
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


class News1Scraper:
    def __init__(self, headless=False):
        """News1 스크래퍼 초기화"""
        self.sections = {
            "politics": "https://www.news1.kr/politics",
            "society": "https://www.news1.kr/society",
            "economy": "https://www.news1.kr/economy",
            "world": "https://www.news1.kr/world",
            "local": "https://www.news1.kr/local",
            "diplomacy": "https://www.news1.kr/diplomacy",
            "nk": "https://www.news1.kr/nk",
            "finance": "https://www.news1.kr/finance",
            "industry": "https://www.news1.kr/industry",
            "realestate": "https://www.news1.kr/realestate",
            "it-science": "https://www.news1.kr/it-science",
            "life-culture": "https://www.news1.kr/life-culture",
        }

        self.section_names = {
            "politics": "정치",
            "society": "사회",
            "economy": "경제",
            "world": "국제",
            "local": "지역",
            "diplomacy": "외교",
            "nk": "북한",
            "finance": "금융",
            "industry": "산업",
            "realestate": "부동산",
            "it-science": "IT/과학",
            "life-culture": "생활/문화",
        }

        self.articles_data = []

        # Chrome 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # 드라이버 초기화
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

        # 결과 저장 디렉토리 생성
        if not os.path.exists("results"):
            os.makedirs("results")

    def scroll_and_click_more(self, max_clicks=10):
        """더보기 버튼을 클릭하여 추가 기사 로드"""
        click_count = 0

        while click_count < max_clicks:
            try:
                # 더보기 버튼 찾기
                more_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.read-more.btn.btn-dark"))
                )

                # 버튼으로 스크롤
                self.driver.execute_script("arguments[0].scrollIntoView(true);", more_button)
                time.sleep(1)

                # 버튼 클릭
                self.driver.execute_script("arguments[0].click();", more_button)
                click_count += 1
                logger.info(f"  더보기 버튼 클릭 {click_count}회")

                # 새 콘텐츠 로딩 대기
                time.sleep(2)

            except (TimeoutException, NoSuchElementException):
                logger.info("  더 이상 로드할 기사가 없습니다.")
                break
            except Exception as e:
                logger.error(f"  더보기 버튼 클릭 중 오류: {e}")
                break

        return click_count

    def extract_article_list(self):
        """최신기사 목록 추출"""
        articles = []

        try:
            # 최신기사 섹션 찾기
            article_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.row-bottom-border-2")

            for container in article_containers:
                try:
                    article_info = {}

                    # 제목과 링크
                    title_elem = container.find_element(By.CSS_SELECTOR, "h2.n1-header-title-1-2 a")
                    article_info["title"] = title_elem.text.strip()
                    article_info["url"] = title_elem.get_attribute("href")

                    # 중복 제거를 위한 URL 체크
                    if not article_info["url"]:
                        continue

                    # 시간
                    try:
                        time_elem = container.find_element(By.CSS_SELECTOR, "div.entry-meta span:first-child")
                        article_info["time"] = time_elem.text.strip()
                    except:
                        article_info["time"] = ""

                    # 기자명
                    try:
                        meta_spans = container.find_elements(By.CSS_SELECTOR, "div.entry-meta span")
                        reporters = []
                        for span in meta_spans:
                            text = span.text.strip()
                            if "기자" in text:
                                reporters.append(text)
                        article_info["reporter"] = ", ".join(reporters) if reporters else ""
                    except:
                        article_info["reporter"] = ""

                    # 요약 (있는 경우)
                    try:
                        desc_elem = container.find_element(By.CSS_SELECTOR, "span.n1-header-desc-1")
                        article_info["description"] = desc_elem.text.strip()
                    except:
                        article_info["description"] = ""

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

            # 본문 로딩 대기 및 기자명 추출
            time.sleep(2)

            content = ""
            category = ""
            # 기자명 추출 (기사 상단)
            try:
                report_elems = self.driver.find_elements(By.CSS_SELECTOR, "div.box--report-top a.report-by")
                reporters = [elem.text.strip() for elem in report_elems]
                reporter = ", ".join(reporters)
            except:
                reporter = ""

            try:
                # 카테고리 추출
                breadcrumb = self.driver.find_elements(By.CSS_SELECTOR, "nav.breadcrumb a")
                if len(breadcrumb) > 1:
                    category = breadcrumb[1].text.strip()
            except:
                category = ""

            try:
                # 본문 추출
                content_elem = self.wait.until(EC.presence_of_element_located((By.ID, "articleBodyContent")))

                # p 태그들의 텍스트 추출
                paragraphs = content_elem.find_elements(By.TAG_NAME, "p")
                content_parts = []

                for p in paragraphs:
                    text = p.text.strip()
                    # 기자 이메일이나 특정 패턴 제외
                    if text and not text.endswith("@news1.kr") and "뉴스1" not in text[:20]:
                        content_parts.append(text)

                content = " ".join(content_parts)

            except Exception as e:
                logger.error(f"  본문 추출 실패: {e}")
                content = ""

            # 발행일 추출
            pub_date = ""
            try:
                pub_elem = self.driver.find_element(By.CSS_SELECTOR, "time#published")
                dt_val = pub_elem.get_attribute("datetime")
                if dt_val:
                    dt_obj = datetime.fromisoformat(dt_val)
                    pub_date = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    pub_date = pub_elem.text.strip()
            except:
                pub_date = ""
            # 탭 닫기
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            return content, category, reporter, pub_date

        except Exception as e:
            logger.error(f"  기사 내용 추출 중 오류: {e}")
            # 오류 발생 시 메인 탭으로 돌아가기
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return "", "", "", ""

    def scrape_section(self, section_key, section_url, max_articles=30, load_more_clicks=3):
        """특정 섹션 스크래핑"""
        section_name = self.section_names.get(section_key, section_key)
        logger.info(f"\n{'='*50}")
        logger.info(f"섹션 스크래핑 시작: {section_name} ({section_url})")
        logger.info(f"{'='*50}")

        try:
            # 페이지 로드
            self.driver.get(section_url)
            time.sleep(3)

            # 더보기 버튼 클릭하여 추가 기사 로드
            self.scroll_and_click_more(load_more_clicks)

            # 기사 목록 추출
            articles = self.extract_article_list()

            # 지정된 수만큼만 처리
            articles_to_process = articles[:max_articles]

            logger.info(f"{len(articles_to_process)}개 기사 상세 정보 수집 시작")

            section_articles = []
            for idx, article in enumerate(articles_to_process, 1):
                logger.info(f"  [{idx}/{len(articles_to_process)}] {article['title'][:30]}...")

                # 본문, 카테고리, 기자명, 발행일 추출
                content, category, page_reporter, pub_date = self.extract_article_content(article["url"])

                # 카테고리가 비어있으면 섹션 이름 사용
                if not category:
                    category = section_name

                # 데이터 저장: 발행일 우선, 없으면 현재 시간 사용
                date_val = pub_date if pub_date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                article_data = {
                    "언론사": "News1",
                    "제목": article["title"],
                    "날짜": date_val,
                    "카테고리": category,
                    "기자명": page_reporter or article.get("reporter", ""),
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
        logger.info(f"News1 멀티 섹션 스크래핑 시작")
        logger.info(f"대상 섹션: {', '.join([self.section_names.get(s, s) for s in sections_to_scrape])}")
        logger.info(f"섹션당 최대 기사 수: {max_articles_per_section}")
        logger.info(f"{'#'*60}")

        start_time = datetime.now()

        for section_key in sections_to_scrape:
            if section_key in self.sections:
                self.scrape_section(section_key, self.sections[section_key], max_articles_per_section, load_more_clicks)
                # 섹션 간 대기 시간
                time.sleep(2)
            else:
                logger.warning(f"알 수 없는 섹션: {section_key}")

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
        filename = f"results/News1_전체_{timestamp}.csv"

        # CSV 저장: '섹션' 컬럼 제거, 지정된 순서 유지
        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
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
        scraper = News1Scraper(headless=False)

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
