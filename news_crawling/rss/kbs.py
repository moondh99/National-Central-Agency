from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime
import os
import requests


# KBS 뉴스 섹션 설정
KBS_SECTIONS = {
    "politics": {"code": "0003", "name": "정치"},
    "economy": {"code": "0004", "name": "경제"},
    "society": {"code": "0005", "name": "사회"},
    "international": {"code": "0008", "name": "국제"},
    "it_science": {"code": "0007", "name": "IT·과학"},
    "culture": {"code": "0006", "name": "문화"},
}


def setup_chrome_driver(headless=True):
    """
    Chrome WebDriver 설정
    headless: 브라우저 창을 숨길지 여부
    """
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Chrome WebDriver 설정 오류: {e}")
        return None


def build_kbs_url(section_code, date_str, page_num=1):
    """
    KBS 뉴스 URL 생성
    section_code: 섹션 코드 (예: '0003')
    date_str: 날짜 문자열 (예: '20250815')
    page_num: 페이지 번호
    """
    base_url = "https://news.kbs.co.kr/news/pc/category/category.do"
    url = f"{base_url}?ctcd={section_code}&ref=pSiteMap#{date_str}&{page_num}"
    return url


def get_kbs_articles_from_page(driver, section_code, section_name, date_str, page_num=1):
    """
    KBS 뉴스 특정 페이지에서 기사 정보 수집
    """
    url = build_kbs_url(section_code, date_str, page_num)

    try:
        print(f"  [{section_name}] 페이지 {page_num} 로딩 중... ({url})")
        # 페이지 로드 또는 페이지 버튼 클릭
        if page_num == 1:
            driver.get(url)
        else:
            try:
                # 페이지 네비게이션 버튼 클릭
                btn = driver.find_element(By.CSS_SELECTOR, f"ul.number-buttons button[data-page='{page_num}']")
                driver.execute_script("arguments[0].click();", btn)
            except Exception as e:
                print(f"  [{section_name}] 페이지 {page_num} 버튼 클릭 실패 ({e}), URL로 이동")
                driver.get(url)
        # 페이지 로딩 대기
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        # 현재 URL 확인 (디버깅용)
        print(f"  [{section_name}] 현재 URL: {driver.current_url}")
        time.sleep(3)  # JavaScript 로딩 대기

        # 페이지 소스 가져오기
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # box-contents 패턴을 모든 페이지에서 추출
        container = soup.find("div", class_="box-contents has-wrap")
        if container:
            link_elems = container.find_all("a", class_="box-content flex-style")
            articles = []
            for elem in link_elems:
                # 제목
                title_tag = elem.find("p", class_="title")
                title = title_tag.get_text().strip() if title_tag else ""
                # 링크
                href = elem.get("href", "")
                if href.startswith("/"):
                    link = "https://news.kbs.co.kr" + href
                else:
                    link = href
                if title and link:
                    articles.append({"title": title, "link": link, "section": section_name})
            print(f"  [{section_name}] box-contents에서 {len(articles)}개 기사 추출 완료")
            return articles

        # KBS 뉴스 기사 리스트 찾기 (여러 패턴 시도)
        articles = []

        article_patterns = [
            soup.find_all("div", class_=lambda x: x and "news" in str(x).lower()),
            soup.find_all("li", class_=lambda x: x and "news" in str(x).lower()),
            soup.find_all("div", class_=lambda x: x and "list" in str(x).lower()),
            soup.find_all("article"),
            soup.find_all("a", href=lambda x: x and "/news/" in str(x)),
        ]

        found_articles = []
        for pattern in article_patterns:
            if pattern and len(pattern) > 0:
                found_articles = pattern
                break

        print(f"  [{section_name}] 페이지 {page_num}에서 {len(found_articles)}개 요소 발견")

        for article_elem in found_articles:
            try:
                # 제목 찾기
                title = ""
                title_patterns = [
                    article_elem.find("h3"),
                    article_elem.find("h4"),
                    article_elem.find("strong"),
                    article_elem.find("a", title=True),
                    article_elem.find(string=True),
                ]

                for title_elem in title_patterns:
                    if title_elem:
                        if hasattr(title_elem, "get_text"):
                            title = title_elem.get_text().strip()
                        elif hasattr(title_elem, "get"):
                            title = title_elem.get("title", "").strip()
                        else:
                            title = str(title_elem).strip()

                        if title and len(title) > 10:  # 의미있는 제목만
                            break

                # 링크 찾기
                link = ""
                link_elem = article_elem.find("a", href=True)
                if link_elem:
                    href = link_elem.get("href")
                    if href:
                        if href.startswith("/"):
                            link = "https://news.kbs.co.kr" + href
                        elif not href.startswith("http"):
                            link = "https://news.kbs.co.kr/" + href
                        else:
                            link = href

                if title and link:
                    articles.append({"title": title, "link": link, "section": section_name})

            except Exception as e:
                continue

        print(f"  [{section_name}] 페이지 {page_num}에서 {len(articles)}개 기사 추출")
        return articles

    except TimeoutException:
        print(f"  [{section_name}] 페이지 {page_num} 로딩 타임아웃")
        return []
    except Exception as e:
        print(f"  [{section_name}] 페이지 {page_num} 처리 중 오류: {e}")
        return []


def extract_kbs_article_detail(article_url, section_name):
    """
    KBS 뉴스 개별 기사에서 상세 정보 추출
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 언론사명
        media_name = "KBS"

        # 제목 추출: headline-title 우선
        title = ""
        headline_elem = soup.find("h4", class_="headline-title")
        if headline_elem:
            title = headline_elem.get_text().strip()
        else:
            # 기존 제목 패턴
            title_patterns = [
                soup.find("h1"),
                soup.find("h2", class_=lambda x: x and "title" in str(x).lower()),
                soup.find("div", class_=lambda x: x and "title" in str(x).lower()),
            ]
            for title_elem in title_patterns:
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title:
                        break

        # 날짜 추출
        date = ""
        date_patterns = [
            soup.find("meta", {"property": "article:published_time"}),
            soup.find("meta", {"name": "article:published_time"}),
            soup.find("time"),
            soup.find("span", class_=lambda x: x and "date" in str(x).lower()),
            soup.find("div", class_=lambda x: x and "date" in str(x).lower()),
        ]

        for date_elem in date_patterns:
            if date_elem:
                date_text = ""
                if date_elem.name == "meta":
                    date_text = date_elem.get("content", "")
                else:
                    date_text = date_elem.get_text().strip()

                if date_text:
                    date = date_text
                    # ISO 형식 변환 시도
                    try:
                        if "T" in date and ("+" in date or "Z" in date):
                            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                            date = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                    break

        # 기자명 추출
        author = ""
        author_patterns = [
            soup.find("meta", {"name": "author"}),
            soup.find("span", string=re.compile(r"기자|특파원|앵커")),
            soup.find("div", string=re.compile(r"기자|특파원|앵커")),
            soup.find("p", string=re.compile(r"기자|특파원|앵커")),
        ]

        for author_elem in author_patterns:
            if author_elem:
                if author_elem.name == "meta":
                    author = author_elem.get("content", "")
                else:
                    author_text = author_elem.get_text().strip()
                    # 기자명 추출
                    author_match = re.search(r"([가-힣]{2,4})\s*(기자|특파원|앵커)", author_text)
                    if author_match:
                        author = author_match.group(1)
                    else:
                        author = author_text

                if author:
                    break

        # 본문 추출
        content = ""
        content_patterns = [
            soup.find("div", {"id": "cont_newstext"}),
            soup.find("div", class_=lambda x: x and "content" in str(x).lower()),
            soup.find("div", class_=lambda x: x and "article" in str(x).lower()),
            soup.find("div", class_=lambda x: x and "text" in str(x).lower()),
        ]

        for content_elem in content_patterns:
            if content_elem:
                # 불필요한 태그 제거
                for script in content_elem(["script", "style", "aside", "nav"]):
                    script.decompose()

                content = content_elem.get_text().strip()
                if content:
                    content = re.sub(r"\s+", " ", content)
                    break

        return {
            "언론사명": media_name,
            "제목": title,
            "날짜": date,
            "카테고리": section_name,
            "기자명": author,
            "본문": content,
        }

    except Exception as e:
        print(f"    기사 상세 정보 추출 오류 ({article_url}): {e}")
        return {"언론사명": "KBS", "제목": "", "날짜": "", "카테고리": section_name, "기자명": "", "본문": ""}


def crawl_kbs_section(driver, section_key, date_str, max_pages=20):
    """
    KBS 특정 섹션의 모든 페이지 크롤링
    """
    section_info = KBS_SECTIONS[section_key]
    section_code = section_info["code"]
    section_name = section_info["name"]

    print(f"\n{'='*20} [KBS {section_name}] 섹션 크롤링 시작 {'='*20}")
    print(f"날짜: {date_str} (페이지 제한 없음)")

    all_articles = []
    collected_urls = set()

    # 페이지 번호 무제한 반복
    page = 1
    while True:
        print(f"\n--- [KBS {section_name}] 페이지 {page} 처리 중 ---")

        # 페이지에서 기사 목록 수집
        page_articles = get_kbs_articles_from_page(driver, section_code, section_name, date_str, page)

        if not page_articles:
            print(f"[KBS {section_name}] 페이지 {page}에서 기사를 찾을 수 없습니다. 크롤링 종료.")
            break

        # 새로운 기사만 처리
        new_articles = [art for art in page_articles if art["link"] not in collected_urls]

        if not new_articles:
            print(f"[KBS {section_name}] 페이지 {page}에 새로운 기사가 없습니다. 크롤링 종료.")
            break

        print(f"[KBS {section_name}] 페이지 {page}에서 {len(new_articles)}개 새 기사 발견")

        # 각 기사의 상세 정보 추출
        for i, article in enumerate(new_articles):
            print(f"    [{section_name}] 기사 {i+1}/{len(new_articles)} 처리 중...")

            detail_info = extract_kbs_article_detail(article["link"], section_name)

            if detail_info["제목"]:  # 제목이 있는 경우만 추가
                all_articles.append(detail_info)
                collected_urls.add(article["link"])

            # 요청 간격 조절
            time.sleep(0.5)

        print(f"[KBS {section_name}] 페이지 {page} 완료: {len(new_articles)}개 기사 수집")
        # 페이지 간 간격
        time.sleep(2)
        page += 1
    # 모든 페이지 크롤링 완료
    print(f"\n[KBS {section_name}] 섹션 크롤링 완료! 총 {len(all_articles)}개 기사 수집")
    return all_articles


def crawl_all_kbs_sections(date_str, sections_to_crawl=None, max_pages=20, headless=True):
    """
    KBS 모든 섹션 크롤링
    date_str: 날짜 문자열 (YYYYMMDD 형식, 예: '20250815')
    sections_to_crawl: 크롤링할 섹션 리스트 (None이면 모든 섹션)
    max_pages: 각 섹션에서 크롤링할 최대 페이지 수
    headless: 브라우저를 숨길지 여부
    """
    if sections_to_crawl is None:
        sections_to_crawl = list(KBS_SECTIONS.keys())

    print("=" * 60)
    print("KBS 뉴스 다중 섹션 크롤링 프로그램")
    print(f"크롤링 대상 날짜: {date_str}")
    print(f"크롤링 대상 섹션: {', '.join([KBS_SECTIONS[s]['name'] for s in sections_to_crawl])}")
    print("=" * 60)

    # WebDriver 설정
    driver = setup_chrome_driver(headless=headless)
    if not driver:
        print("❌ WebDriver 설정에 실패했습니다.")
        return [], {}

    all_articles = []
    section_results = {}

    try:
        for section_key in sections_to_crawl:
            if section_key not in KBS_SECTIONS:
                print(f"⚠️ 알 수 없는 섹션: {section_key}")
                continue

            try:
                articles = crawl_kbs_section(driver, section_key, date_str, max_pages)
                all_articles.extend(articles)
                section_results[KBS_SECTIONS[section_key]["name"]] = len(articles)

                # 섹션 간 간격
                time.sleep(3)

            except Exception as e:
                print(f"❌ [KBS {KBS_SECTIONS[section_key]['name']}] 섹션 크롤링 중 오류 발생: {e}")
                section_results[KBS_SECTIONS[section_key]["name"]] = 0

    finally:
        driver.quit()
        print("\n브라우저 종료")

    return all_articles, section_results


def save_kbs_to_csv(articles_data, date_str, filename=None, split_by_section=False):
    """
    KBS 뉴스 데이터를 CSV 파일로 저장
    """
    # 강제 단일 파일 저장 (split_by_section 무시)
    split_by_section = False

    if not articles_data:
        print("저장할 데이터가 없습니다.")
        return None

    # DataFrame 생성
    df = pd.DataFrame(articles_data)

    # 열 순서
    column_order = ["언론사명", "제목", "날짜", "카테고리", "기자명", "본문"]
    df = df[column_order]

    # results 디렉토리 생성
    os.makedirs("results", exist_ok=True)

    saved_files = []

    if split_by_section:
        # 섹션별로 파일 저장
        for category in df["카테고리"].unique():
            section_df = df[df["카테고리"] == category]
            section_filename = f"results/KBS_{category}_{date_str}.csv"

            section_df.to_csv(section_filename, index=False, encoding="utf-8-sig")

            print(f"✓ [KBS {category}] CSV 파일 저장 완료: {section_filename}")
            print(f"  - {len(section_df)}개 기사, {os.path.getsize(section_filename):,} bytes")
            saved_files.append(section_filename)
    else:
        # 통합 파일로 저장
        if filename is None:
            filename = f"results/KBS_전체_{date_str}.csv"

        df.to_csv(filename, index=False, encoding="utf-8-sig")

        print(f"✓ KBS 통합 CSV 파일 저장 완료: {filename}")
        print(f"  - 총 {len(df)}개 기사, {os.path.getsize(filename):,} bytes")
        saved_files.append(filename)

    return saved_files


def main():
    """
    메인 실행 함수
    """
    print("KBS 뉴스 크롤링 프로그램을 시작합니다.")
    print("\n사용 가능한 섹션:")
    for key, info in KBS_SECTIONS.items():
        print(f"  - {key}: {info['name']} (코드: {info['code']})")

    # 사용자 설정: 오늘 날짜 자동 사용
    date_str = datetime.now().strftime("%Y%m%d")  # 크롤링할 날짜 (YYYYMMDD)
    sections_to_crawl = None  # 모든 섹션 (특정 섹션: ['politics', 'economy'])
    max_pages = 20  # 각 섹션당 최대 페이지 수
    split_by_section = True  # True: 섹션별 파일, False: 통합 파일
    headless = True  # True: 브라우저 숨김, False: 브라우저 표시

    try:
        # 크롤링 실행
        articles, section_results = crawl_all_kbs_sections(date_str, sections_to_crawl, max_pages, headless)

        if articles:
            # CSV 파일로 저장
            saved_files = save_kbs_to_csv(articles, date_str, split_by_section=split_by_section)

            # 결과 요약
            print("\n" + "=" * 60)
            print("KBS 뉴스 크롤링 완료 결과")
            print("=" * 60)
            print(f"✓ 크롤링 대상 날짜: {date_str}")
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
                print(f"{i+1}. [KBS {row['카테고리']}] {row['제목']}")
                print(f"   기자: {row['기자명']}, 날짜: {row['날짜']}")
                print()

            return saved_files
        else:
            print("❌ 크롤링된 기사가 없습니다.")
            return None

    except Exception as e:
        print(f"❌ 프로그램 실행 중 오류 발생: {e}")
        return None


def crawl_kbs_specific_date_sections(date_str, section_list, max_pages=5):

    articles, section_results = crawl_all_kbs_sections(date_str, section_list, max_pages)

    if articles:
        saved_files = save_kbs_to_csv(articles, date_str, split_by_section=True)
        print(f"\n✅ KBS 뉴스 크롤링 완료: {len(articles)}개 기사 수집")
        return saved_files
    else:
        print("❌ KBS 뉴스 크롤링 실패")
        return None


if __name__ == "__main__":
    # 메인 프로그램 실행
    result_files = main()
