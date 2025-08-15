import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re
import os  # 추가


class CCTodayRSSCollector:
    def __init__(self):
        self.base_url = "https://www.cctoday.co.kr"
        self.rss_feeds = {"전체기사": "https://www.cctoday.co.kr/rss/allArticle.xml"}

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

        # 충청투데이 기자명 패턴들
        patterns = [
            r"(\w+)\s*기자",
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"\[충청투데이\]\s*([가-힣]{2,4})\s*기자",
            r"충청투데이\s*([가-힣]{2,4})\s*기자",
            r"([가-힣]{2,4})\s*연합뉴스",  # 연합뉴스 기자
            r"기자\s*=\s*([가-힣]{2,4})",
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

            # 원문 페이지의 article-view-content-div에서 본문 및 기자명 추출
            article_elem = soup.find("article", id="article-view-content-div")
            if article_elem:
                paragraphs = article_elem.find_all("p")
                texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                if texts:
                    # 마지막 문단에서 기자명 추출
                    reporter = self.extract_reporter_name(texts[-1]) or ""
                    # 본문은 마지막 제외한 모든 문단
                    content = " ".join(texts[:-1])
                    content = self.clean_text(content)
                    print(f"    원문 본문 및 기자({reporter}) 추출 완료")
                    return content, reporter

            # 기사 본문 추출 (충청투데이의 본문 구조에 맞게)
            content_selectors = [
                "article .article-content",
                ".article-content",
                ".news-content",
                "#article-content",
                ".articleCont",
                ".article_cont",
                'div[itemprop="articleBody"]',
                ".article-body",
                ".user-content",
                ".content",
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
            reporter_selectors = [
                ".reporter",
                ".byline",
                ".author",
                ".article-info",
                ".news-info",
                ".article-head",
                ".writer",
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

            for entry in feed.entries[:20]:  # 최대 20개 기사만 처리
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    description = self.clean_text(entry.get("description", ""))
                    pub_date = entry.get("published", "")

                    # 발행일 파싱
                    try:
                        if pub_date:
                            parsed_date = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
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

                    # RSS 피드에서 기자명이 있는지도 확인
                    if not reporter and hasattr(entry, "author"):
                        reporter = self.extract_reporter_name(entry.author)

                    article_data = {
                        "category": category,
                        "title": title,
                        "link": link,
                        "description": description,
                        "content": content,
                        "reporter": reporter,
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

        fieldnames = ["category", "title", "link", "description", "content", "reporter", "pub_date", "collected_at"]

        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(articles)

        print(f"\n총 {len(articles)}개 기사가 {filename}에 저장되었습니다.")

    def run_collection(self):
        """전체 수집 실행"""
        print("충청투데이 RSS 자동 수집 시작...")
        all_articles = []
        for category, rss_url in self.rss_feeds.items():
            all_articles.extend(self.collect_rss_feed(category, rss_url))
            time.sleep(2)
        # 단일 CSV로 저장
        if all_articles:
            os.makedirs("results", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/충청투데이_전체_{timestamp}.csv"
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for art in all_articles:
                    writer.writerow(
                        {
                            "언론사": "충청투데이",
                            "제목": art["title"],
                            "날짜": art["pub_date"],
                            "카테고리": art["category"],
                            "기자명": art["reporter"],
                            "본문": art["content"],
                        }
                    )
            print(f"총 {len(all_articles)}개 기사 저장: {filename}")
        else:
            print("수집된 기사가 없습니다.")


def main():
    """메인 실행 함수"""
    collector = CCTodayRSSCollector()
    collector.run_collection()


if __name__ == "__main__":
    main()
