import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re


class KoreaHeraldRSSCollector:
    def __init__(self):
        self.base_url = "https://www.koreaherald.com"
        # 이미지에서 확인한 RSS 피드 URL들
        self.rss_feeds = {
            "All Stories": "https://www.koreaherald.com/rss/newsAll",
            "National": "https://www.koreaherald.com/rss/kh_National",
            "Business": "https://www.koreaherald.com/rss/kh_Business",
            "Life & Culture": "https://www.koreaherald.com/rss/kh_LifenCulture",
            "Sports": "https://www.koreaherald.com/rss/kh_Sports",
            "World": "https://www.koreaherald.com/rss/kh_World",
            "Opinion": "https://www.koreaherald.com/rss/kh_Opinion",
            "K-pop": "https://www.koreaherald.com/rss/kh_Kpop",
        }

        # 대체 모바일 RSS URL (필요시 사용)
        self.mobile_rss_feeds = {
            "All Stories": "https://m.koreaherald.com/rss/newsAll",
            "National": "https://m.koreaherald.com/rss/kh_National",
            "Business": "https://m.koreaherald.com/rss/kh_Business",
            "Life & Culture": "https://m.koreaherald.com/rss/kh_LifenCulture",
            "Sports": "https://m.koreaherald.com/rss/kh_Sports",
            "World": "https://m.koreaherald.com/rss/kh_World",
            "Opinion": "https://m.koreaherald.com/rss/kh_Opinion",
            "K-pop": "https://m.koreaherald.com/rss/kh_Kpop",
        }

        # User-Agent 리스트 (랜덤 선택용)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
        ]

    def get_random_user_agent(self):
        return random.choice(self.user_agents)

    def clean_text(self, text):
        """텍스트 정제 함수"""
        if not text:
            return ""

        # HTML 태그 제거
        text = re.sub(r"<[^>]+>", "", text)
        # CDATA 제거
        text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
        # 특수문자 정제
        text = re.sub(r"&nbsp;|&lt;|&gt;|&amp;|&quot;|&#39;", " ", text)
        # 여러 공백을 하나로
        text = re.sub(r"\s+", " ", text)
        # 앞뒤 공백 제거
        text = text.strip()

        return text

    def extract_reporter_name(self, text):
        """기자명 추출 함수"""
        if not text:
            return ""

        # Korea Herald 기자명 패턴들
        patterns = [
            r"By\s+([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)",  # By FirstName LastName
            r"([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)\s*\(\s*[a-zA-Z0-9._%+-]+@koreaherald\.com\s*\)",  # Name (email)
            r"([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)\s*-\s*The Korea Herald",
            r"([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)\s*,\s*staff\s*writer",
            r"Staff\s+writer\s+([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)",
            r"([가-힣]{2,4})\s*기자",  # 한국어 기자명
            r"기자\s*([가-힣]{2,4})",
            r"([A-Z][a-z-]+(?:\s+[A-Z][a-z-]+)?)\s*@\s*koreaherald\.com",  # Name @ email
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return ""

    def get_article_content(self, url):
        """개별 기사 본문 추출"""
        try:
            headers = {
                "User-Agent": self.get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            # 기사 본문 추출 (Korea Herald의 본문 구조에 맞게)
            content_selectors = [
                "article .article-content",
                ".article-content",
                ".news-content",
                "#article-content",
                ".articleCont",
                ".article_cont",
                'div[itemprop="articleBody"]',
                ".article-body",
                ".content-body",
                ".story-body",
                ".view_con_t",
                ".article_txt",
            ]

            content = ""
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content = content_element.get_text(strip=True)
                    break

            if not content:
                # 대체 방법: p 태그들에서 본문 추출
                paragraphs = soup.find_all("p")
                content_list = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 30:  # 충분한 길이의 텍스트만
                        content_list.append(text)
                content = " ".join(content_list[:12])  # 처음 12개 문단만

            # 기자명 추출
            reporter = ""
            reporter_selectors = [
                ".reporter",
                ".byline",
                ".author",
                ".article-info",
                ".news-info",
                ".writer-info",
                ".story-byline",
                ".article_writer",
                ".view_con_t .writer",
            ]

            for selector in reporter_selectors:
                reporter_element = soup.select_one(selector)
                if reporter_element:
                    reporter_text = reporter_element.get_text()
                    reporter = self.extract_reporter_name(reporter_text)
                    if reporter:
                        break

            # 기자명을 찾지 못한 경우 본문에서 추출
            if not reporter:
                reporter = self.extract_reporter_name(content)

            return self.clean_text(content), reporter

        except Exception as e:
            print(f"본문 추출 실패 ({url}): {e}")
            return "", ""

    def collect_rss_feed(self, category, rss_url, use_mobile=False):
        """RSS 피드에서 기사 수집"""
        articles = []

        try:
            print(f"\n{category} RSS 피드 수집 중...")

            # 모바일 URL 사용 옵션
            if use_mobile and category in self.mobile_rss_feeds:
                rss_url = self.mobile_rss_feeds[category]
                print(f"모바일 RSS 사용: {rss_url}")

            # RSS 피드 파싱 (User-Agent 포함)
            headers = {"User-Agent": self.get_random_user_agent()}
            response = requests.get(rss_url, headers=headers, timeout=15)

            if response.status_code != 200:
                print(f"RSS 피드 접근 실패 ({response.status_code}): {rss_url}")
                return articles

            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"RSS 피드가 비어있습니다: {rss_url}")
                return articles

            for entry in feed.entries:
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    description = self.clean_text(entry.get("description", ""))
                    pub_date = entry.get("published", "")
                    author = entry.get("author", "")

                    # 발행일 파싱
                    try:
                        if pub_date:
                            # 다양한 날짜 포맷 시도
                            date_formats = [
                                "%a, %d %b %Y %H:%M:%S %Z",
                                "%a, %d %b %Y %H:%M:%S %z",
                                "%Y-%m-%d %H:%M:%S",
                                "%Y-%m-%dT%H:%M:%S",
                            ]

                            for date_format in date_formats:
                                try:
                                    parsed_date = datetime.strptime(pub_date, date_format)
                                    formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                                    break
                                except:
                                    continue
                            else:
                                formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 개별 기사 본문 및 기자명 추출
                    if link:
                        content, reporter = self.get_article_content(link)
                        time.sleep(random.uniform(1.0, 2.0))  # 요청 간격 조절
                    else:
                        content, reporter = description, ""

                    # RSS 피드에서 기자명 추출
                    if not reporter and author:
                        reporter = self.extract_reporter_name(author)

                    article_data = {
                        "category": category,
                        "title": title,
                        "link": link,
                        "description": description,
                        "content": content,
                        "reporter": reporter,
                        "author": author,
                        "pub_date": formatted_date,
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    articles.append(article_data)
                    print(f"수집완료: {title[:50]}...")

                except Exception as e:
                    print(f"기사 처리 중 오류: {e}")
                    continue

        except Exception as e:
            print(f"RSS 피드 수집 실패 ({rss_url}): {e}")

        return articles

    def save_to_csv(self, articles, filename):
        """CSV 파일로 저장"""
        if not articles:
            print("저장할 기사가 없습니다.")
            return

        fieldnames = [
            "category",
            "title",
            "link",
            "description",
            "content",
            "reporter",
            "author",
            "pub_date",
            "collected_at",
        ]

        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(articles)

        print(f"\n총 {len(articles)}개 기사가 {filename}에 저장되었습니다.")

    def run_collection(self, selected_categories=None, use_mobile=False):
        """전체 수집 실행"""
        print("=" * 60)
        print("Korea Herald RSS 뉴스 수집기")
        print("=" * 60)

        # 카테고리 선택
        if selected_categories is None:
            # 기본적으로 주요 카테고리만 수집
            selected_categories = ["National", "Business", "Life & Culture", "Sports", "World", "K-pop", "Opinion"]

        all_articles = []

        # 선택된 카테고리별 RSS 피드 수집
        for category in selected_categories:
            if category in self.rss_feeds:
                rss_url = self.rss_feeds[category]
                articles = self.collect_rss_feed(category, rss_url, use_mobile)
                all_articles.extend(articles)
                time.sleep(3)  # 카테고리 간 대기시간
            else:
                print(f"카테고리를 찾을 수 없습니다: {category}")

        # 결과 저장
        if all_articles:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/koreaherald_news_{timestamp}.csv"
            self.save_to_csv(all_articles, filename)

            # 수집 결과 요약
            print("\n" + "=" * 60)
            print("수집 결과 요약")
            print("=" * 60)

            category_counts = {}
            for article in all_articles:
                category = article["category"]
                category_counts[category] = category_counts.get(category, 0) + 1

            for category, count in category_counts.items():
                print(f"{category}: {count}개")

            print(f"\n전체: {len(all_articles)}개 기사 수집 완료")
            print(f"파일명: {filename}")
        else:
            print("수집된 기사가 없습니다. 모바일 RSS 사용을 시도해보세요.")


def main():
    """메인 실행 함수"""
    collector = KoreaHeraldRSSCollector()

    # 사용 예시 1: 기본 카테고리 수집
    collector.run_collection()

    # 사용 예시 2: 모바일 RSS 사용
    # collector.run_collection(use_mobile=True)

    # 사용 예시 3: 특정 카테고리만 수집
    # collector.run_collection(['National', 'Business', 'K-pop'])

    # 사용 예시 4: 모든 카테고리 수집
    # collector.run_collection(list(collector.rss_feeds.keys()))


if __name__ == "__main__":
    main()
