import os
import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

NEWS_OUTLET = "뉴스톱"
# 모든 기자명 고정
REPORTER_NAME = "팩트체크"


class NewstofCrawlerImproved:
    def __init__(self):
        self.base_url = "https://www.newstof.com"
        self.list_url = "https://www.newstof.com/news/articleList.html"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_total_pages(self):
        """전체 페이지 수 계산"""
        params = {"sc_section_code": "S1N45", "view_type": "sm", "page": 1}

        try:
            response = self.session.get(self.list_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # 총 건수 찾기
            total_text = soup.find(text=re.compile(r"총.*\d+.*건"))
            if total_text:
                total_count = int(re.search(r"(\d{1,3}(?:,\d{3})*)", total_text).group(1).replace(",", ""))
                total_pages = (total_count + 19) // 20
                logging.info(f"총 {total_count}건의 기사, {total_pages}페이지")
                return total_pages
            else:
                logging.warning("총 건수를 찾을 수 없습니다. 기본값 169페이지 사용")
                return 169

        except Exception as e:
            logging.error(f"페이지 수 계산 중 오류: {e}")
            return 169

    def get_article_links_from_page(self, page_num):
        """특정 페이지에서 기사 링크와 기본 정보 추출"""
        params = {"sc_section_code": "S1N45", "view_type": "sm", "page": page_num}

        try:
            response = self.session.get(self.list_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            articles_info = []

            # 요약형 view에서 기사 정보 추출
            article_items = soup.find_all("li")

            for item in article_items:
                # 기사 링크 찾기
                link_elem = item.find("a", href=re.compile(r"articleView\.html\?idxno=\d+"))
                if not link_elem:
                    continue

                article_url = urljoin(self.base_url, link_elem["href"])

                # 리스트 페이지에서 미리 날짜와 기자명 추출 시도
                date_text = ""
                reporter_text = ""

                # 날짜 패턴 찾기 (예: 2025.06.27 16:01)
                date_elem = item.find(text=re.compile(r"\d{4}\.\d{2}\.\d{2}"))
                if date_elem:
                    date_match = re.search(r"(\d{4}\.\d{2}\.\d{2})", date_elem.strip())
                    if date_match:
                        date_text = date_match.group(1)

                # 기자명 패턴 찾기
                reporter_elem = item.find(text=re.compile(r"[가-힣]+\s*기자"))
                if reporter_elem:
                    reporter_match = re.search(r"([가-힣]+)\s*기자", reporter_elem.strip())
                    if reporter_match:
                        reporter_text = reporter_match.group(1)

                articles_info.append({"url": article_url, "preview_date": date_text, "preview_reporter": reporter_text})

            # 중복 제거
            seen_urls = set()
            unique_articles = []
            for article in articles_info:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    unique_articles.append(article)

            logging.info(f"페이지 {page_num}: {len(unique_articles)}개 기사 링크 발견")
            return unique_articles

        except Exception as e:
            logging.error(f"페이지 {page_num} 링크 추출 중 오류: {e}")
            return []

    def clean_content(self, content):
        """본문 내용 정제"""
        if not content:
            return "내용 없음"

        # 불필요한 텍스트 패턴들
        patterns_to_remove = [
            r"이 기사를 공유합니다[\s\S]*?닫기",
            r"페이스북\(으\)로 기사보내기",
            r"트위터\(으\)로 기사보내기",
            r"URL복사\(으\)로 기사보내기",
            r"공유\s*스크랩\s*인쇄",
            r"본문 글씨 줄이기\s*본문 글씨 키우기",
            r"저작권자.*?무단전재.*?금지",
            r"다른기사 보기",
            r"관련기사[\s\S]*?$",
            r"^\s*닫기\s*",
            r"^\s*공유\s*",
            r"^\s*스크랩\s*",
            r"^\s*인쇄\s*",
        ]

        # 패턴 제거
        for pattern in patterns_to_remove:
            content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)

        # 연속된 공백 및 줄바꿈 정리
        content = re.sub(r"\n\s*\n", "\n", content)
        content = re.sub(r"\s+", " ", content)

        # 앞뒤 공백 제거
        content = content.strip()

        return content

    def extract_article_content(self, article_info):
        """개별 기사 내용 추출 (개선된 버전)"""
        article_url = article_info["url"]

        try:
            response = self.session.get(article_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # 제목 추출 (개선된 방법)
            title_selectors = [
                "h1",
                "h2.article-title",
                ".article-head-title h1",
                ".article-head-title h2",
                ".news-title",
                ".article-header h1",
            ]

            title = "제목 없음"
            detected_category = "기타"
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    raw_title = title_elem.get_text(strip=True)
                    # 카테고리 감지 (제목 프리픽스 기반)
                    if re.search(r"주간\s*팩트\s*체크|주간팩트체크", raw_title):
                        detected_category = "주간팩트체크"
                    elif re.search(r"팩트\s*체크|팩트체크", raw_title):
                        detected_category = "팩트체크"

                    # 표제 정리: 프리픽스 제거
                    title = re.sub(r"^\[?팩트\s*체크\]?\s*", "", raw_title)
                    title = re.sub(r"^\[?주간\s*팩트\s*체크\]?\s*", "", title)
                    break

            # 날짜 추출 (개선된 방법)
            date = article_info.get("preview_date", "")
            if not date:
                # 기사 페이지에서 다시 시도
                date_selectors = [".article-head-info", ".article-info", ".news-info", ".date-info", "time"]

                for selector in date_selectors:
                    date_elem = soup.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text()
                        date_match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", date_text)
                        if date_match:
                            year, month, day = date_match.groups()
                            date = f"{year}.{month.zfill(2)}.{day.zfill(2)}"
                            break

                # datetime 속성에서 추출 시도
                if not date:
                    datetime_elem = soup.find(attrs={"datetime": True})
                    if datetime_elem:
                        datetime_str = datetime_elem.get("datetime")
                        try:
                            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                            date = dt.strftime("%Y.%m.%d")
                        except:
                            pass

            # 기자명: RSS author(preview_reporter)만 사용
            reporter = article_info.get("preview_reporter", "")

            # 본문 내용 추출 (개선된 방법)
            content_selectors = [
                # 원문 컨테이너(우선순위 최상)
                'article#article-view-content-div[itemprop="articleBody"]',
                "#article-view-content-div",
                ".article-content",
                ".news-content",
                ".article-body",
                ".content-body",
                'div[id*="content"]',
                ".article-text",
            ]

            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 불필요한 태그 제거
                    for tag in content_elem(
                        [
                            "script",
                            "style",
                            "nav",
                            "header",
                            "footer",
                            "aside",
                            "figure",
                            "img",
                            "figcaption",
                            "iframe",
                            "table",
                        ]
                    ):
                        tag.decompose()

                    # 관련기사, 공유버튼 등 제거
                    for unwanted in content_elem.select(
                        '.share-button, .related-articles, .ad, .advertisement, .ad-template, [id^="AD"]'
                    ):
                        unwanted.decompose()

                    content = content_elem.get_text(separator="\n", strip=True)
                    break

            # 본문을 찾지 못한 경우 대체 방법
            if not content or len(content) < 100:
                # 메인 컨텐츠 영역 찾기
                main_content = soup.find("main") or soup.find("article") or soup.find(".main-content")
                if main_content:
                    for tag in main_content(["script", "style", "nav", "header", "footer"]):
                        tag.decompose()
                    content = main_content.get_text(separator="\n", strip=True)

            # 본문 정제
            content = self.clean_content(content)

            # 본문 길이 제한 (너무 긴 경우)
            if len(content) > 5000:
                content = content[:5000] + "..."

            # 카테고리 기본값 보정 (섹션 자체가 팩트체크이므로 미검출시 팩트체크로 지정)
            if detected_category == "기타":
                detected_category = "팩트체크"

            return {
                "title": title,
                "date": date,
                "content": content if content else "내용 추출 실패",
                "reporter": reporter,
                "url": article_url,
                "category": detected_category,
            }

        except Exception as e:
            logging.error(f"기사 추출 중 오류 ({article_url}): {e}")
            return {
                "title": "추출 실패",
                "date": article_info.get("preview_date", ""),
                "content": f"오류: {str(e)}",
                "reporter": article_info.get("preview_reporter", ""),
                "url": article_url,
                "category": "기타",
            }

    def crawl_all_articles(self, output_file="results/newstof_factcheck_improved.csv", max_pages=None):
        """모든 팩트체크 기사 크롤링 (개선된 버전)"""
        total_pages = self.get_total_pages()
        if max_pages:
            total_pages = min(total_pages, max_pages)

        all_articles = []
        processed_count = 0

        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["제목", "날짜", "본문내용", "기자명", "URL"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for page in range(1, total_pages + 1):
                logging.info(f"페이지 {page}/{total_pages} 처리 중...")

                # 페이지에서 기사 정보 추출
                articles_info = self.get_article_links_from_page(page)

                for i, article_info in enumerate(articles_info):
                    logging.info(f"  기사 {i+1}/{len(articles_info)} 처리 중: {article_info['url']}")

                    # 기사 내용 추출
                    article_data = self.extract_article_content(article_info)

                    # CSV에 쓰기
                    writer.writerow(
                        {
                            "제목": article_data["title"],
                            "날짜": article_data["date"],
                            "본문내용": article_data["content"],
                            "기자명": article_data["reporter"],
                            "URL": article_data["url"],
                        }
                    )

                    all_articles.append(article_data)
                    processed_count += 1

                    # 요청 간 딜레이 (서버 부하 방지)
                    time.sleep(1)

                # 페이지 간 딜레이
                time.sleep(2)

                # 중간 저장 로그 (10페이지마다)
                if page % 10 == 0:
                    successful_dates = sum(1 for article in all_articles if article["date"])
                    successful_reporters = sum(1 for article in all_articles if article["reporter"])
                    logging.info(f"{page}페이지까지 처리 완료. 총 {processed_count}개 기사 수집.")
                    logging.info(
                        f"날짜 추출 성공률: {successful_dates}/{processed_count} ({successful_dates/processed_count*100:.1f}%)"
                    )
                    logging.info(
                        f"기자명 추출 성공률: {successful_reporters}/{processed_count} ({successful_reporters/processed_count*100:.1f}%)"
                    )

        # 최종 통계
        successful_dates = sum(1 for article in all_articles if article["date"])
        successful_reporters = sum(1 for article in all_articles if article["reporter"])

        logging.info(f"크롤링 완료! 총 {len(all_articles)}개 기사가 {output_file}에 저장되었습니다.")
        logging.info(
            f"최종 날짜 추출 성공률: {successful_dates}/{len(all_articles)} ({successful_dates/len(all_articles)*100:.1f}%)"
        )
        logging.info(
            f"최종 기자명 추출 성공률: {successful_reporters}/{len(all_articles)} ({successful_reporters/len(all_articles)*100:.1f}%)"
        )

        return all_articles

    def crawl_per_category(self, categories=None, max_per_category=20, output_dir="results"):
        """카테고리별로 20개씩 자동 수집하여 단일 CSV로 저장

        - 카테고리 감지는 제목의 프리픽스([팩트체크], [주간팩트체크]) 기반
        - 기본 카테고리: ['팩트체크', '주간팩트체크']
        - 출력 컬럼: 언론사, 제목, 날짜, 카테고리, 기자명, 본문
        """
        if categories is None:
            categories = ["팩트체크", "주간팩트체크"]

        # 수집 상태
        collected = {cat: [] for cat in categories}
        counts = {cat: 0 for cat in categories}
        seen_urls = set()

        # 출력 준비
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"{NEWS_OUTLET}_전체_{timestamp}.csv")

        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        total_pages = self.get_total_pages()

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            page = 1
            while page <= total_pages and any(counts[cat] < max_per_category for cat in categories):
                logging.info(f"카테고리별 수집 진행 중... 페이지 {page}/{total_pages}")
                articles_info = self.get_article_links_from_page(page)

                for article_info in articles_info:
                    if all(counts[cat] >= max_per_category for cat in categories):
                        break

                    if article_info["url"] in seen_urls:
                        continue

                    data = self.extract_article_content(article_info)
                    seen_urls.add(article_info["url"])

                    cat = data.get("category", "기타")
                    # 카테고리 매칭: 감지된 카테고리가 지정 카테고리 중 하나인 경우만 집계
                    if cat not in categories:
                        continue

                    if counts[cat] >= max_per_category:
                        continue

                    # 쓰기
                    writer.writerow(
                        {
                            "언론사": NEWS_OUTLET,
                            "제목": data.get("title", ""),
                            "날짜": data.get("date", ""),
                            "카테고리": cat,
                            "기자명": REPORTER_NAME,
                            "본문": data.get("content", ""),
                        }
                    )

                    collected[cat].append(data)
                    counts[cat] += 1

                    logging.info(f"수집: {cat} {counts[cat]}/{max_per_category}  |  {data.get('title','')[:40]}")

                    # 요청 간 딜레이
                    time.sleep(1)

                # 페이지 간 딜레이
                page += 1
                time.sleep(2)

        # 요약 로그
        for cat in categories:
            logging.info(f"카테고리 '{cat}' 수집 완료: {counts[cat]}개")

        logging.info(f"저장 완료: {output_file}")
        return collected


def main():
    crawler = NewstofCrawlerImproved()
    try:
        # 비대화형: 각 카테고리(팩트체크/주간팩트체크) 20개씩 자동 수집하여 단일 CSV 저장
        crawler.crawl_per_category(
            categories=["팩트체크", "주간팩트체크"],
            max_per_category=20,
            output_dir="results",
        )
        print("수집 완료: 카테고리별 20개씩 저장했습니다.")
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"크롤링 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
