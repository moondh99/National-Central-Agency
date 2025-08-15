import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re
import os  # 추가


class CCTimesRSSCollector:
    def __init__(self):
        self.base_url = "http://www.cctimes.kr"
        self.rss_feeds = {"전체기사": "http://www.cctimes.kr/rss/allArticle.xml"}

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

        # 충청타임즈 기자명 패턴들
        patterns = [
            r"(\w+)\s*기자",
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"\[충청타임즈\]\s*([가-힣]{2,4})\s*기자",
            r"충청타임즈\s*([가-힣]{2,4})\s*기자",
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

            # 원문 페이지의 article-view-content-div에서 본문 우선 추출
            article_div = soup.find("div", id="article-view-content-div")
            if article_div:
                # 본문 추출
                paragraphs = article_div.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                content = self.clean_text(content)
                # 기자명 추출
                reporter_elem = soup.select_one("#article-view-content-div .view-editors strong")
                if reporter_elem:
                    reporter = reporter_elem.get_text(strip=True).replace(" 기자", "")
                else:
                    reporter = self.extract_reporter_name(content)
                print(f"    원문 본문 및 기자({reporter}) 추출 완료")
                return content, reporter

            # 기사 본문 추출 (충청타임즈의 본문 구조에 맞게)
            content_selectors = [
                "article .article-content",
                ".article-content",
                ".news-content",
                "#article-content",
                ".articleCont",
                ".article_cont",
                'div[itemprop="articleBody"]',
                ".article-body",
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
                content = " ".join(content_list[:10])  # 처음 10개 문단만

            # 기자명 추출
            reporter = ""
            reporter_selectors = [".reporter", ".byline", ".author", ".article-info", ".news-info"]

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

    def collect_rss_feed(self, category, rss_url):
        """RSS 피드에서 기사 수집"""
        articles = []

        try:
            print(f"\n{category} RSS 피드 수집 중...")

            feed = feedparser.parse(rss_url)
            if not feed.entries:
                print(f"RSS 피드가 비어있습니다: {rss_url}")
                return articles

            for entry in feed.entries[:20]:  # 최대 20개 기사만 처리
                try:
                    title = self.clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    pub_date = entry.get("published", "")
                    # 날짜 포맷
                    try:
                        if pub_date:
                            parsed = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
                            date = parsed.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 기자명: RSS author
                    author = entry.get("author", "")
                    reporter = self.extract_reporter_name(author)
                    if not reporter:
                        reporter = "미상"
                    # 본문 추출
                    if link:
                        content, _ = self.get_article_content(link)
                        time.sleep(random.uniform(0.5, 1.5))
                    else:
                        content = self.clean_text(entry.get("description", ""))
                    if len(content.strip()) < 20:
                        print(f"    ⚠ 본문 짧아 건너뜀: {title[:30]}")
                        continue
                    articles.append(
                        {"category": category, "title": title, "date": date, "reporter": reporter, "content": content}
                    )
                    print(f"    수집완료: {title[:30]}")
                except Exception as e:
                    print(f"기사 처리 중 오류: {e}")
                    continue
        except Exception as e:
            print(f"RSS 피드 수집 실패 ({rss_url}): {e}")
        return articles

    def run_collection(self):
        """전체 수집 실행"""
        print("=" * 60)
        print("충청타임즈(cctimes.kr) RSS 뉴스 수집기")
        print("=" * 60)

        all_articles = []
        for category, rss_url in self.rss_feeds.items():
            all_articles.extend(self.collect_rss_feed(category, rss_url))
            time.sleep(2)

        # CSV 저장
        if all_articles:
            os.makedirs("results", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/충청타임즈_전체_{timestamp}.csv"
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for art in all_articles:
                    writer.writerow(
                        {
                            "언론사": "충청타임즈",
                            "제목": art["title"],
                            "날짜": art["date"],
                            "카테고리": art["category"],
                            "기자명": art["reporter"],
                            "본문": art["content"],
                        }
                    )
            print(f"\n총 {len(all_articles)}개 기사 저장: {filename}")
        else:
            print("수집된 기사가 없습니다.")


def main():
    """메인 실행 함수"""
    collector = CCTimesRSSCollector()
    collector.run_collection()


if __name__ == "__main__":
    main()
