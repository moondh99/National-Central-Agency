import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import time
import random
import re
from datetime import datetime
import csv
from urllib.parse import urljoin, urlparse
import logging


class SegyeNewsRSSCrawler:
    def __init__(self):
        """세계일보 RSS 크롤러 초기화"""
        self.base_url = "https://www.segye.com"

        # 세계일보 본지 RSS 피드 (11개)
        self.segye_feeds = {
            "전체뉴스": "https://www.segye.com/Articles/RSSList/segye_recent.xml",
            "정치": "https://www.segye.com/Articles/RSSList/segye_politic.xml",
            "경제": "https://www.segye.com/Articles/RSSList/segye_economy.xml",
            "사회": "https://www.segye.com/Articles/RSSList/segye_society.xml",
            "국제": "https://www.segye.com/Articles/RSSList/segye_international.xml",
            "전국": "https://www.segye.com/Articles/RSSList/segye_local.xml",
            "문화": "https://www.segye.com/Articles/RSSList/segye_culture.xml",
            "오피니언": "https://www.segye.com/Articles/RSSList/segye_opinion.xml",
        }

        # 전체 RSS 피드 목록
        self.all_feeds = self.segye_feeds

        # 매체별 분류 (현재 세계일보만 지원)
        self.media_classification = {
            "세계일보": list(self.segye_feeds.keys()),
        }

        # 카테고리 그룹 분류
        self.category_groups = {
            "종합뉴스": ["전체뉴스", "SW_전체뉴스", "SF_전체뉴스"],
            "정치·사회": ["정치", "사회", "국제", "전국"],
            "경제·금융": ["경제", "SF_금융", "SF_산업", "SF_부동산", "SF_증권"],
            "문화·연예": ["문화", "연예", "SW_연예"],
            "스포츠·라이프": ["스포츠", "SW_스포츠", "SW_라이프"],
            "오피니언": ["오피니언", "SF_오피니언"],
            "특별": ["포토", "SF_CSR"],
        }

        # User-Agent 리스트
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]

        self.articles = []
        self.session = requests.Session()

        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 헤더 생성"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": "https://www.segye.com/",
        }

    def random_delay(self, min_delay=1, max_delay=3):
        """랜덤 딜레이"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    def fetch_rss_feed(self, rss_url, max_retries=3):
        """RSS 피드 가져오기"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(rss_url, headers=headers, timeout=30)
                response.raise_for_status()

                # 인코딩 처리
                if response.encoding.lower() in ["euc-kr", "cp949"]:
                    response.encoding = "euc-kr"
                else:
                    response.encoding = "utf-8"

                return response.text
            except Exception as e:
                self.logger.warning(f"RSS 피드 가져오기 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(2, 5)
                else:
                    self.logger.error(f"RSS 피드 가져오기 최종 실패: {rss_url}")
                    return None

    def parse_rss_feed(self, rss_content):
        """RSS 피드 파싱"""
        try:
            root = ET.fromstring(rss_content)
            items = []

            for item in root.findall(".//item"):
                article_info = {}

                # 기본 정보 추출
                title_elem = item.find("title")
                article_info["title"] = title_elem.text.strip() if title_elem is not None else ""

                link_elem = item.find("link")
                article_info["link"] = link_elem.text.strip() if link_elem is not None else ""

                pubdate_elem = item.find("pubDate")
                article_info["pub_date"] = pubdate_elem.text.strip() if pubdate_elem is not None else ""

                # author/creator 추출
                author_elem = item.find("author")
                if author_elem is None:
                    author_elem = item.find(".//{http://purl.org/dc/elements/1.1/}creator")
                article_info["author"] = author_elem.text.strip() if author_elem is not None else ""

                # description에서 간단한 내용 추출
                desc_elem = item.find("description")
                if desc_elem is not None:
                    desc_text = desc_elem.text or ""
                    # CDATA 처리
                    if desc_text.startswith("<![CDATA[") and desc_text.endswith("]]>"):
                        desc_text = desc_text[9:-3]

                    # HTML 태그 제거하여 텍스트만 추출
                    soup = BeautifulSoup(desc_text, "html.parser")
                    article_info["description"] = (
                        soup.get_text().strip()[:300] + "..."
                        if len(soup.get_text().strip()) > 300
                        else soup.get_text().strip()
                    )
                else:
                    article_info["description"] = ""

                items.append(article_info)

            return items
        except Exception as e:
            self.logger.error(f"RSS 파싱 오류: {e}")
            return []

    def extract_article_content(self, article_url, max_retries=3):
        """개별 기사 본문 추출 - 세계일보 계열 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()

                # 인코딩 처리
                if "segye.com" in article_url:
                    response.encoding = "utf-8"
                elif "sportsworld.com" in article_url:
                    response.encoding = "utf-8"
                elif "segyefn.com" in article_url:
                    response.encoding = "utf-8"

                soup = BeautifulSoup(response.text, "html.parser")

                # 세계일보 계열 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    "article.viewBox2[itemprop='articleBody']",  # Segye 원문 본문
                    'article[itemprop="articleBody"]',  # 일반 itemprop 본문
                    ".article-content",  # 세계일보 기사 내용
                    ".news-content",  # 뉴스 내용
                    ".view-content",  # 뷰 내용
                    ".article-body",  # 기사 본문
                    ".content-body",  # 본문 내용
                    ".news-text",  # 뉴스 텍스트
                    ".article_content",  # 기사 콘텐츠
                    ".view_content",  # 뷰 콘텐츠
                    "#article-view-content-div",  # 특정 ID
                    ".article_view",  # 기사 뷰
                ]

                content = ""
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        # 요약(em.precis) 제거
                        for em in content_elem.find_all("em", class_="precis"):
                            em.decompose()
                        # 요약 섹션 제거
                        for sec in content_elem.find_all("section"):
                            sec.decompose()
                        content = content_elem.get_text().strip()
                        break

                # 본문이 없으면 전체 텍스트에서 추출 시도
                if not content:
                    # 헤더, 푸터, 사이드바 등 제거
                    for elem in soup.find_all(["header", "footer", "nav", "aside", "script", "style"]):
                        elem.decompose()

                    main_content = soup.find("main") or soup.find("div", class_="content") or soup.find("body")
                    if main_content:
                        content = main_content.get_text().strip()

                # 기자명 추출: 지정된 경로에서 우선 추출
                reporter_elem = soup.select_one(
                    "body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > section > div:nth-of-type(1) > div:nth-of-type(1) > article > div"
                )
                if reporter_elem and reporter_elem.get_text().strip():
                    reporter = reporter_elem.get_text().strip()
                else:
                    reporter = self.extract_reporter_name(soup, content)

                # 키워드 추출
                keywords = self.extract_keywords(content)

                # 텍스트 정리
                content = re.sub(r"\s+", " ", content).strip()

                return {
                    "content": content[:3000] + "..." if len(content) > 3000 else content,
                    "reporter": reporter,
                    "keywords": keywords,
                }

            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {"content": "추출 실패", "reporter": "", "keywords": ""}

    def extract_reporter_name(self, soup, content):
        """기자명 추출"""
        # 세계일보 계열 기자명 추출 패턴
        reporter_patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"기자\s*:\s*([가-힣]{2,4})",
            r"취재\s*:\s*([가-힣]{2,4})",
            r"글\s*:\s*([가-힣]{2,4})",
            r"작성자\s*:\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*논설위원",
        ]

        # HTML에서 기자명 찾기
        reporter_selectors = [".reporter-name", ".author-name", ".writer-name", ".byline", ".reporter", ".author"]

        for selector in reporter_selectors:
            reporter_elem = soup.select_one(selector)
            if reporter_elem:
                reporter_text = reporter_elem.get_text().strip()
                # 기자로 끝나는 전체 문구 추출
                for pattern in reporter_patterns:
                    match = re.search(pattern, reporter_text)
                    if match:
                        return match.group(0).strip()  # e.g., '홍준표 기자'
                return reporter_text

        # 텍스트에서 기자명 패턴 매칭
        for pattern in reporter_patterns:
            # 본문에서 기자로 끝나는 문장 찾기
            match = re.search(pattern, content)
            if match:
                return match.group(0).strip()

        return ""

    def extract_keywords(self, content):
        """키워드 추출"""
        # 주요 키워드 패턴
        keyword_patterns = [
            r"(정부|국회|대통령|총리|장관)",
            r"(경제|금융|증시|부동산|산업)",
            r"(문화|예술|영화|음악|방송)",
            r"(스포츠|올림픽|월드컵|리그)",
            r"(교육|대학|학교|학생)",
            r"(의료|건강|병원|의사)",
            r"(환경|기후|에너지|탄소)",
            r"(IT|인공지능|디지털|메타버스)",
        ]

        keywords = set()
        for pattern in keyword_patterns:
            matches = re.findall(pattern, content)
            keywords.update(matches)

        return ", ".join(list(keywords)[:10])  # 최대 10개 키워드

    def get_media_name(self, category_name):
        """카테고리명으로 매체명 반환"""
        for media, categories in self.media_classification.items():
            if category_name in categories:
                return media
        return "기타"

    def get_category_group(self, category_name):
        """카테고리의 그룹 반환"""
        for group, categories in self.category_groups.items():
            if category_name in categories:
                return group
        return "기타"

    def crawl_category_feed(self, category, rss_url, max_items=30):
        """개별 카테고리 RSS 피드 크롤링"""
        media_name = self.get_media_name(category)
        self.logger.info(f"{media_name} - {category} 크롤링 시작")

        # RSS 피드 가져오기
        rss_content = self.fetch_rss_feed(rss_url)
        if not rss_content:
            return

        # RSS 파싱
        rss_items = self.parse_rss_feed(rss_content)
        if not rss_items:
            self.logger.warning(f"RSS 아이템이 없습니다: {category}")
            return

        # 지정된 개수만큼만 처리
        items_to_process = rss_items[:max_items]

        for i, item in enumerate(items_to_process, 1):
            try:
                self.logger.info(f"{category} 기사 처리 중: {i}/{len(items_to_process)} - {item['title'][:50]}...")

                # 기사 상세 내용 추출
                if item["link"]:
                    article_detail = self.extract_article_content(item["link"])

                    article_data = {
                        "media": media_name,
                        "category": category,
                        "category_group": self.get_category_group(category),
                        "title": item["title"],
                        "link": item["link"],
                        "pub_date": item["pub_date"],
                        "author": item["author"],
                        "description": item["description"],
                        "content": article_detail["content"],
                        # 기자명을 '세계일보'로 통일
                        "reporter": "세계일보",
                        "keywords": article_detail["keywords"],
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    self.articles.append(article_data)

                # 딜레이
                self.random_delay(1, 3)

            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue

        self.logger.info(f"{category} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_feeds(self, max_items_per_category=30):
        """모든 RSS 피드 크롤링"""
        total_categories = len(self.all_feeds)
        self.logger.info(f"전체 {total_categories}개 세계일보 계열 RSS 피드 크롤링 시작")

        for i, (category, rss_url) in enumerate(self.all_feeds.items(), 1):
            try:
                media_name = self.get_media_name(category)
                self.logger.info(f"[{i}/{total_categories}] {media_name} - {category} 피드 크롤링 중...")
                self.crawl_category_feed(category, rss_url, max_items_per_category)

                # 카테고리 간 딜레이
                if i < total_categories:
                    self.random_delay(2, 4)

            except Exception as e:
                self.logger.error(f"{category} 카테고리 크롤링 오류: {e}")
                continue

        self.logger.info(f"전체 세계일보 계열 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_categories(self, category_names, max_items_per_category=30):
        """특정 카테고리들만 크롤링"""
        for category_name in category_names:
            if category_name in self.all_feeds:
                self.crawl_category_feed(category_name, self.all_feeds[category_name], max_items_per_category)
            else:
                self.logger.warning(f"존재하지 않는 카테고리: {category_name}")
                available_categories = list(self.all_feeds.keys())
                self.logger.info(f"사용 가능한 카테고리: {available_categories}")

    def crawl_by_media(self, media_names, max_items_per_category=25):
        """매체별 크롤링"""
        target_categories = []

        for media_name in media_names:
            if media_name in self.media_classification:
                target_categories.extend(self.media_classification[media_name])
            else:
                self.logger.warning(f"존재하지 않는 매체: {media_name}")

        if target_categories:
            self.logger.info(f"매체 '{', '.join(media_names)}'에 해당하는 카테고리: {target_categories}")
            self.crawl_specific_categories(target_categories, max_items_per_category)
        else:
            self.logger.warning(f"해당 매체에 맞는 카테고리를 찾을 수 없습니다: {media_names}")

    def crawl_by_group(self, groups, max_items_per_category=25):
        """그룹별 카테고리 크롤링"""
        target_categories = []

        for group in groups:
            if group in self.category_groups:
                target_categories.extend(self.category_groups[group])
            else:
                self.logger.warning(f"존재하지 않는 그룹: {group}")

        if target_categories:
            self.logger.info(f"그룹 '{', '.join(groups)}'에 해당하는 카테고리: {target_categories}")
            self.crawl_specific_categories(target_categories, max_items_per_category)
        else:
            self.logger.warning(f"해당 그룹에 맞는 카테고리를 찾을 수 없습니다: {groups}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/세계일보_전체_{timestamp}.csv"

        try:
            df = pd.DataFrame(self.articles)
            # 필요한 열만 선택하고 순서 지정
            df_out = df[["media", "title", "pub_date", "category", "reporter", "content"]].rename(
                columns={
                    "media": "언론사",
                    "title": "제목",
                    "pub_date": "날짜",
                    "category": "카테고리",
                    "reporter": "기자명",
                    "content": "본문",
                }
            )
            df_out.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_media(self):
        """매체별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for media in df["media"].unique():
            media_df = df[df["media"] == media]
            filename = f"results/{media}_{timestamp}.csv"
            media_df.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"{media} 저장 완료: {filename} ({len(media_df)}개 기사)")

    def save_by_category(self):
        """카테고리별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for category in df["category"].unique():
            category_df = df[df["category"] == category]
            media_name = category_df["media"].iloc[0]
            filename = f"results/{media_name}_{category}_{timestamp}.csv"
            category_df.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"{category} 저장 완료: {filename} ({len(category_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return

        df = pd.DataFrame(self.articles)

        print("\n" + "=" * 60)
        print("세계일보 계열 RSS 크롤링 통계")
        print("=" * 60)

        # 매체별 통계
        media_stats = df["media"].value_counts()
        print(f"\n📰 매체별 기사 수:")
        for media, count in media_stats.items():
            print(f"  • {media}: {count}개")

        # 카테고리별 통계
        category_stats = df["category"].value_counts()
        print(f"\n📊 카테고리별 기사 수:")
        for category, count in category_stats.items():
            media_name = df[df["category"] == category]["media"].iloc[0]
            print(f"  • {category} ({media_name}): {count}개")

        # 그룹별 통계
        group_stats = df["category_group"].value_counts()
        print(f"\n🗂️ 그룹별 기사 수:")
        for group, count in group_stats.items():
            print(f"  • {group}: {count}개")

        # 기자별 통계 (상위 10명)
        reporter_stats = df[df["reporter"] != ""]["reporter"].value_counts().head(10)
        if not reporter_stats.empty:
            print(f"\n✍️ 주요 기자별 기사 수:")
            for reporter, count in reporter_stats.items():
                print(f"  • {reporter} 기자: {count}개")

        # 키워드 통계
        keyword_stats = df[df["keywords"] != ""]["keywords"].str.split(", ").explode().value_counts().head(10)
        if not keyword_stats.empty:
            print(f"\n🔍 주요 키워드별 언급 수:")
            for keyword, count in keyword_stats.items():
                print(f"  • {keyword}: {count}회")

        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 매체 수: {len(media_stats)}개")
        print(f"  • 크롤링 카테고리 수: {len(category_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 기자명 추출: {len(df[df['reporter'] != ''])}개")
        print(f"  • 키워드 추출: {len(df[df['keywords'] != ''])}개")
        print("=" * 60)

    def get_available_categories(self):
        """사용 가능한 카테고리 목록 반환"""
        return list(self.all_feeds.keys())

    def get_media_list(self):
        """매체 목록 반환"""
        return list(self.media_classification.keys())

    def get_groups(self):
        """그룹 목록 반환"""
        return list(self.category_groups.keys())


def main():
    """메인 실행 함수"""
    print("세계일보 계열 RSS 크롤러")
    print("=" * 50)

    crawler = SegyeNewsRSSCrawler()

    print("전체 세계일보 계열 RSS 피드 크롤링을 시작합니다...")
    crawler.crawl_all_feeds(max_items_per_category=20)

    # CSV 저장
    crawler.save_to_csv()

    print("\n세계일보 계열 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
