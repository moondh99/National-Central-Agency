import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re


class KoreaTimesRSSCollector:
    def __init__(self):
        self.base_url = "https://www.koreatimes.co.kr"
        self.rss_feeds = {
            "All News": "https://feed.koreatimes.co.kr/k/allnews.xml",
            "Foreign Affairs": "https://feed.koreatimes.co.kr/k/foreignaffairs.xml",
            "Entertainment": "https://feed.koreatimes.co.kr/k/entertainment.xml",
            "Opinion": "https://feed.koreatimes.co.kr/k/opinion.xml",
            "South Korea": "https://feed.koreatimes.co.kr/k/southkorea.xml",
            "Economy": "https://feed.koreatimes.co.kr/k/economy.xml",
            "Business": "https://feed.koreatimes.co.kr/k/business.xml",
            "Lifestyle": "https://feed.koreatimes.co.kr/k/lifestyle.xml",
            "Sports": "https://feed.koreatimes.co.kr/k/sports.xml",
            "World": "https://feed.koreatimes.co.kr/k/world.xml",
            "Video": "https://feed.koreatimes.co.kr/k/video.xml",
            "Photos": "https://feed.koreatimes.co.kr/k/photos.xml",
        }

        # User-Agent 리스트 (랜덤 선택용)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
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

    def extract_reporter_name(self, text, author_info=None):
        """기자명 추출 함수"""
        if not text and not author_info:
            return ""

        # author 정보에서 먼저 추출 시도
        if author_info:
            # 이메일에서 기자명 추출
            email_patterns = [r"([a-zA-Z0-9]+)@koreatimes\.co\.kr", r"([a-zA-Z]+)@koreatimes\.co\.kr"]

            for pattern in email_patterns:
                match = re.search(pattern, author_info)
                if match:
                    return match.group(1)

        # 본문에서 기자명 패턴 추출
        if text:
            patterns = [
                r"By\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",  # By FirstName LastName
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*staff\s*writer",
                r"([가-힣]{2,4})\s*기자",
                r"기자\s*([가-힣]{2,4})",
                r"Staff\s+writer\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*@koreatimes\.co\.kr",
            ]

            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)

        return ""

    def get_article_content(self, url):
        """개별 기사 본문 추출"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            # 기사 본문 추출 (Korea Times의 본문 구조에 맞게)
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
                    if len(text) > 20:  # 충분한 길이의 텍스트만
                        content_list.append(text)
                content = " ".join(content_list[:15])  # 처음 15개 문단만

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
            ]

            for selector in reporter_selectors:
                reporter_element = soup.select_one(selector)
                if reporter_element:
                    reporter_text = reporter_element.get_text()
                    reporter = self.extract_reporter_name(reporter_text)
                    if reporter:
                        break

            return self.clean_text(content), reporter

        except Exception as e:
            print(f"본문 추출 실패 ({url}): {e}")
            return "", ""

    def collect_rss_feed(self, category, rss_url):
        """RSS 피드에서 기사 수집"""
        articles = []

        try:
            print(f"\n{category} RSS 피드 수집 중...")

            # RSS 피드 파싱
            feed = feedparser.parse(rss_url)

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
                            # RSS 날짜 포맷: Sun, 03 Aug 2025 06:27:03 GMT
                            parsed_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                            formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 개별 기사 본문 및 기자명 추출
                    if link:
                        content, reporter = self.get_article_content(link)
                        time.sleep(random.uniform(0.5, 1.5))  # 요청 간격 조절
                    else:
                        content, reporter = description, ""

                    # RSS 피드에서 기자명 추출 (author 정보 활용)
                    if not reporter:
                        reporter = self.extract_reporter_name("", author)

                    # 본문에서 기자명 재추출
                    if not reporter:
                        reporter = self.extract_reporter_name(content)

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

    def run_collection(self, selected_categories=None):
        """전체 수집 실행"""
        print("=" * 60)
        print("Korea Times RSS 뉴스 수집기")
        print("=" * 60)

        # 카테고리 선택
        if selected_categories is None:
            # 기본적으로 주요 카테고리만 수집 (All News는 너무 많으므로 제외)
            selected_categories = [
                "South Korea",
                "Business",
                "Economy",
                "Foreign Affairs",
                "Entertainment",
                "Sports",
                "Opinion",
            ]

        all_articles = []

        # 선택된 카테고리별 RSS 피드 수집
        for category in selected_categories:
            if category in self.rss_feeds:
                rss_url = self.rss_feeds[category]
                articles = self.collect_rss_feed(category, rss_url)
                all_articles.extend(articles)
                time.sleep(2)  # 카테고리 간 대기시간
            else:
                print(f"카테고리를 찾을 수 없습니다: {category}")

        # 결과 저장
        if all_articles:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/koreatimes_news_{timestamp}.csv"
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
            print("수집된 기사가 없습니다.")


def main():
    """메인 실행 함수"""
    collector = KoreaTimesRSSCollector()

    # 사용 예시 1: 기본 카테고리 수집
    collector.run_collection()

    # 사용 예시 2: 특정 카테고리만 수집
    # collector.run_collection(['All News', 'South Korea', 'Business'])

    # 사용 예시 3: 모든 카테고리 수집 (시간이 오래 걸림)
    # collector.run_collection(list(collector.rss_feeds.keys()))


if __name__ == "__main__":
    main()
