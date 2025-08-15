import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime
import os


# 섹션 설정
SECTIONS = {
    "politics": {"url": "https://www.joongang.co.kr/politics", "name": "정치"},
    "money": {"url": "https://www.joongang.co.kr/money", "name": "경제"},
    "society": {"url": "https://www.joongang.co.kr/society", "name": "사회"},
    "world": {"url": "https://www.joongang.co.kr/world", "name": "국제"},
    "culture": {"url": "https://www.joongang.co.kr/culture", "name": "문화"},
}


def get_article_urls_from_page(section_key, page_num=1):
    """
    중앙일보 특정 섹션에서 기사 URL들을 수집
    section_key: 섹션 키 ('politics', 'money', 'society', 'world', 'culture')
    page_num: 페이지 번호 (1부터 시작)
    """
    section_info = SECTIONS[section_key]

    if page_num == 1:
        url = section_info["url"]
    else:
        url = f"{section_info['url']}?page={page_num}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 기사 링크들 수집
        article_links = soup.find_all("a", href=re.compile(r"/article/\d+"))

        urls = []
        for link in article_links:
            href = link.get("href")
            if href:
                if href.startswith("/"):
                    href = "https://www.joongang.co.kr" + href
                urls.append(href)

        # 중복 제거
        unique_urls = list(set(urls))

        print(f"[{section_info['name']}] 페이지 {page_num}에서 {len(unique_urls)}개의 기사 URL 수집 완료")
        return unique_urls

    except Exception as e:
        print(f"[{section_info['name']}] 페이지 {page_num} 수집 중 오류 발생: {e}")
        return []


def extract_article_info(article_url, section_name):
    """
    개별 기사 URL에서 상세 정보를 추출
    article_url: 기사 URL
    section_name: 섹션명 (정치, 경제, 사회, 국제, 문화)
    반환값: dict (언론사명, 제목, 날짜, 카테고리, 기자명, 본문)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 언론사명 - 고정값
        media_name = "중앙일보"

        # 제목 추출
        title = ""
        title_elem = soup.find("h1")
        if title_elem:
            title = title_elem.get_text().strip()

        # 날짜 추출 (메타 태그에서)
        date = ""
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta:
            date = date_meta.get("content", "")
            # ISO 형식을 한국 형식으로 변환
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    date = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

        # 카테고리 - 섹션명 사용
        category = section_name

        # 기자명 추출 (메타 태그에서)
        author = ""
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta:
            author = author_meta.get("content", "")

        # 본문 추출
        content = ""
        article_body = soup.find("div", {"id": "article_body"}) or soup.find("div", class_="article_body")
        if article_body:
            # 불필요한 태그들 제거 후 텍스트 추출
            for script in article_body(["script", "style", "aside", "nav"]):
                script.decompose()
            content = article_body.get_text().strip()
            # 여러 공백과 줄바꿈을 정리
            content = re.sub(r"\s+", " ", content)

        article_data = {
            "언론사명": media_name,
            "제목": title,
            "날짜": date,
            "카테고리": category,
            "기자명": author,
            "본문": content,
        }

        return article_data

    except Exception as e:
        print(f"[{section_name}] 기사 추출 중 오류 발생 ({article_url}): {e}")
        return {"언론사명": "중앙일보", "제목": "", "날짜": "", "카테고리": section_name, "기자명": "", "본문": ""}


def crawl_section(section_key, max_pages=5):
    """
    특정 섹션을 크롤링
    section_key: 섹션 키
    max_pages: 크롤링할 최대 페이지 수
    """
    section_info = SECTIONS[section_key]
    section_name = section_info["name"]

    print(f"\n{'='*20} [{section_name}] 섹션 크롤링 시작 {'='*20}")

    all_articles = []
    all_urls = set()  # 중복 URL 방지

    for page in range(1, max_pages + 1):
        print(f"\n=== [{section_name}] 페이지 {page} 크롤링 중 ===")

        # 기사 URL들 수집
        urls = get_article_urls_from_page(section_key, page)

        if not urls:
            print(f"[{section_name}] 페이지 {page}에서 기사를 찾을 수 없습니다.")
            break

        # 새로운 URL만 처리
        new_urls = [url for url in urls if url not in all_urls]
        print(f"[{section_name}] 새로운 기사 {len(new_urls)}개 발견")

        if not new_urls:
            print(f"[{section_name}] 더 이상 새로운 기사가 없습니다.")
            break

        # 각 기사의 상세 정보 추출
        for i, url in enumerate(new_urls):
            print(f"  [{section_name}] 기사 {i+1}/{len(new_urls)} 처리 중...")
            article_data = extract_article_info(url, section_name)

            if article_data["제목"]:  # 제목이 추출된 경우만 추가
                all_articles.append(article_data)
                all_urls.add(url)

            # 요청 간격 조절 (서버 부하 방지)
            time.sleep(0.5)

        print(f"[{section_name}] 페이지 {page} 완료: {len(new_urls)}개 기사 수집")

        # 페이지 간 간격
        time.sleep(1)

    print(f"\n[{section_name}] 섹션 크롤링 완료! 총 {len(all_articles)}개 기사 수집")
    return all_articles


def crawl_all_sections(sections_to_crawl=None, max_pages=5):
    """
    여러 섹션을 크롤링
    sections_to_crawl: 크롤링할 섹션 리스트 (None이면 모든 섹션)
    max_pages: 각 섹션에서 크롤링할 최대 페이지 수
    """
    if sections_to_crawl is None:
        sections_to_crawl = list(SECTIONS.keys())

    print("=" * 60)
    print("중앙일보 다중 섹션 크롤링 프로그램")
    print(f"크롤링 대상 섹션: {', '.join([SECTIONS[s]['name'] for s in sections_to_crawl])}")
    print("=" * 60)

    all_articles = []
    section_results = {}

    for section_key in sections_to_crawl:
        if section_key not in SECTIONS:
            print(f"⚠️ 알 수 없는 섹션: {section_key}")
            continue

        try:
            articles = crawl_section(section_key, max_pages)
            all_articles.extend(articles)
            section_results[SECTIONS[section_key]["name"]] = len(articles)

            # 섹션 간 간격
            time.sleep(2)

        except Exception as e:
            print(f"❌ [{SECTIONS[section_key]['name']}] 섹션 크롤링 중 오류 발생: {e}")
            section_results[SECTIONS[section_key]["name"]] = 0

    return all_articles, section_results


def save_to_csv(articles_data, filename=None, split_by_section=False):
    """
    기사 데이터를 CSV 파일로 저장
    articles_data: 기사 데이터 리스트
    filename: 파일명 (None이면 자동 생성)
    split_by_section: 섹션별로 파일을 나누어 저장할지 여부
    """
    # 강제 단일 파일 저장 (split_by_section 무시)
    split_by_section = False

    if not articles_data:
        print("저장할 데이터가 없습니다.")
        return None

    # DataFrame 생성
    df = pd.DataFrame(articles_data)

    # 열 순서는 요구사항에 맞게: 언론사명, 제목, 날짜, 카테고리, 기자명, 본문
    column_order = ["언론사명", "제목", "날짜", "카테고리", "기자명", "본문"]
    df = df[column_order]

    # results 디렉토리 생성
    os.makedirs("results", exist_ok=True)

    saved_files = []

    if split_by_section:
        # 섹션별로 파일 저장
        for category in df["카테고리"].unique():
            section_df = df[df["카테고리"] == category]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            section_filename = f"results/중앙일보_{category}_{timestamp}.csv"

            # CSV 파일로 저장 (UTF-8 with BOM for Excel compatibility)
            section_df.to_csv(section_filename, index=False, encoding="utf-8-sig")

            print(f"✓ [{category}] CSV 파일 저장 완료: {section_filename}")
            print(f"  - {len(section_df)}개 기사, {os.path.getsize(section_filename):,} bytes")
            saved_files.append(section_filename)
    else:
        # 통합 파일로 저장
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/중앙일보_전체_{timestamp}.csv"

        # CSV 파일로 저장 (UTF-8 with BOM for Excel compatibility)
        df.to_csv(filename, index=False, encoding="utf-8-sig")

        print(f"✓ 통합 CSV 파일 저장 완료: {filename}")
        print(f"  - 총 {len(df)}개 기사, {os.path.getsize(filename):,} bytes")
        saved_files.append(filename)

    return saved_files


def main():
    """
    메인 실행 함수
    """
    print("중앙일보 다중 섹션 크롤링 프로그램을 시작합니다.")
    print("\n사용 가능한 섹션:")
    for key, info in SECTIONS.items():
        print(f"  - {key}: {info['name']}")

    # 사용자 설정 (여기서 수정 가능)
    # 모든 섹션 크롤링: None
    # 특정 섹션만 크롤링: ['politics', 'money'] 등
    sections_to_crawl = None  # 모든 섹션
    max_pages = 5  # 각 섹션당 최대 페이지 수
    split_by_section = False  # 통합 파일만 저장

    try:
        # 크롤링 실행
        articles, section_results = crawl_all_sections(sections_to_crawl, max_pages)

        if articles:
            # CSV 파일로 저장
            saved_files = save_to_csv(articles, split_by_section=split_by_section)

            # 결과 요약
            print("\n" + "=" * 60)
            print("크롤링 완료 결과")
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

            print(f"\n📰 최신 기사 5개 (전체 섹션):")
            # 날짜순으로 정렬
            df_sorted = df.sort_values("날짜", ascending=False)
            for i in range(min(5, len(df_sorted))):
                row = df_sorted.iloc[i]
                print(f"{i+1}. [{row['카테고리']}] {row['제목']}")
                print(f"   기자: {row['기자명']}, 날짜: {row['날짜']}")
                print()

            return saved_files
        else:
            print("❌ 크롤링된 기사가 없습니다.")
            return None

    except Exception as e:
        print(f"❌ 프로그램 실행 중 오류 발생: {e}")
        return None


def crawl_specific_sections(section_list, max_pages=5, split_files=True):

    articles, section_results = crawl_all_sections(section_list, max_pages)

    if articles:
        saved_files = save_to_csv(articles, split_by_section=split_files)
        print(f"\n✅ 크롤링 완료: {len(articles)}개 기사 수집")
        return saved_files
    else:
        print("❌ 크롤링 실패")
        return None


if __name__ == "__main__":
    # 메인 프로그램 실행
    result_files = main()
