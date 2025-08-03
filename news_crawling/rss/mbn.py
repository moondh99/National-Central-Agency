import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re


class MBNRSSCollector:
    def __init__(self):
        self.base_url = "https://www.mbn.co.kr"

        # 뉴스 카테고리 RSS 피드
        self.news_rss_feeds = {
            "전체기사": "http://www.mbn.co.kr/rss/",
            "정치": "http://www.mbn.co.kr/rss/politics/",
            "경제": "http://www.mbn.co.kr/rss/economy/",
            "사회": "http://www.mbn.co.kr/rss/society/",
            "국제": "http://www.mbn.co.kr/rss/international/",
            "문화": "http://www.mbn.co.kr/rss/culture/",
            "연예": "http://www.mbn.co.kr/rss/enter/",
            "스포츠": "http://www.mbn.co.kr/rss/sports/",
            "생활·건강": "http://www.mbn.co.kr/rss/health/",
        }

        # 영상 카테고리 RSS 피드
        self.video_rss_feeds = {
            "MBN종합뉴스": "http://www.mbn.co.kr/rss/vod/vod_rss_552.xml",
            "굿모닝MBN": "http://www.mbn.co.kr/rss/vod/vod_rss_605.xml",
            "아침&매일경제": "http://www.mbn.co.kr/rss/vod/vod_rss_606.xml",
            "뉴스파이터": "http://www.mbn.co.kr/rss/vod/vod_rss_673.xml",
            "MBN프레스룸": "http://www.mbn.co.kr/rss/vod/vod_rss_812.xml",
            "MBN뉴스와이드": "http://www.mbn.co.kr/rss/vod/vod_rss_536.xml",
        }

        # 전체 RSS 피드 (뉴스 + 영상)
        self.all_rss_feeds = {**self.news_rss_feeds, **self.video_rss_feeds}

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

    def extract_reporter_name(self, text):
        """기자명 추출 함수"""
        if not text:
            return ""

        # MBN 기자명 패턴들
        patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"\[([가-힣]{2,4})\s*기자\]",
            r"MBN\s*([가-힣]{2,4})\s*기자",
            r"\/\s*([가-힣]{2,4})\s*기자",
            r"([가-힣]{2,4})\s*@\s*mbn\.co\.kr",
            r"([가-힣]{2,4})\s*연합뉴스",  # 연합뉴스 기자
            r"([가-힣]{2,4})\s*MBN",
            r"\[([가-힣]{2,4})@mbn\.co\.kr\]",
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

            # 기사 본문 추출 (MBN의 본문 구조에 맞게)
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
                ".view_con_t",
                ".article_txt",
                ".news_content",
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
                ".writer-info",
                ".article_writer",
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

            for entry in feed.entries:
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    description = self.clean_text(entry.get("description", ""))
                    pub_date = entry.get("published", "")
                    author = entry.get("author", "")
                    category_info = entry.get("category", "")

                    # 발행일 파싱
                    try:
                        if pub_date:
                            # MBN RSS 날짜 포맷: Thu, 31 Jul 2025 07:07:00 +0900
                            parsed_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
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

                    # RSS 피드에서 기자명 추출
                    if not reporter and author:
                        reporter = self.extract_reporter_name(author)

                    # 영상 콘텐츠 여부 판단
                    is_video = category in self.video_rss_feeds

                    article_data = {
                        "category": category,
                        "title": title,
                        "link": link,
                        "description": description,
                        "content": content,
                        "reporter": reporter,
                        "author": author,
                        "rss_category": category_info,
                        "is_video": is_video,
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
            "rss_category",
            "is_video",
            "pub_date",
            "collected_at",
        ]

        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(articles)

        print(f"\n총 {len(articles)}개 기사가 {filename}에 저장되었습니다.")

    def run_collection(self, content_type="news", selected_categories=None):
        """전체 수집 실행"""
        print("=" * 60)
        print("MBN RSS 뉴스 수집기")
        print("=" * 60)

        # 컨텐츠 타입에 따른 RSS 피드 선택
        if content_type == "news":
            rss_feeds = self.news_rss_feeds
            print("뉴스 콘텐츠 수집 모드")
        elif content_type == "video":
            rss_feeds = self.video_rss_feeds
            print("영상 콘텐츠 수집 모드")
        else:  # 'all'
            rss_feeds = self.all_rss_feeds
            print("전체 콘텐츠 수집 모드")

        # 선택된 카테고리만 수집
        if selected_categories:
            rss_feeds = {k: v for k, v in rss_feeds.items() if k in selected_categories}

        all_articles = []

        # 각 카테고리별 RSS 피드 수집
        for category, rss_url in rss_feeds.items():
            articles = self.collect_rss_feed(category, rss_url)
            all_articles.extend(articles)
            time.sleep(2)  # 카테고리 간 대기시간

        # 결과 저장
        if all_articles:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_type_suffix = f"_{content_type}" if content_type != "all" else ""
            filename = f"results/mbn{content_type_suffix}_news_{timestamp}.csv"
            self.save_to_csv(all_articles, filename)

            # 수집 결과 요약
            print("\n" + "=" * 60)
            print("수집 결과 요약")
            print("=" * 60)

            category_counts = {}
            video_count = 0
            news_count = 0

            for article in all_articles:
                category = article["category"]
                category_counts[category] = category_counts.get(category, 0) + 1

                if article["is_video"]:
                    video_count += 1
                else:
                    news_count += 1

            for category, count in category_counts.items():
                content_type_mark = "[영상]" if category in self.video_rss_feeds else "[뉴스]"
                print(f"{content_type_mark} {category}: {count}개")

            print(f"\n뉴스 기사: {news_count}개")
            print(f"영상 콘텐츠: {video_count}개")
            print(f"전체: {len(all_articles)}개")
            print(f"파일명: {filename}")
        else:
            print("수집된 콘텐츠가 없습니다.")


def main():
    """메인 실행 함수"""
    collector = MBNRSSCollector()

    # 사용 예시 1: 뉴스만 수집
    collector.run_collection(content_type="news")

    # 사용 예시 2: 영상만 수집
    # collector.run_collection(content_type='video')

    # 사용 예시 3: 전체 수집 (뉴스 + 영상)
    # collector.run_collection(content_type='all')

    # 사용 예시 4: 특정 카테고리만 수집
    # collector.run_collection(content_type='news', selected_categories=['정치', '경제', '사회'])

    # 사용 예시 5: 특정 영상 프로그램만 수집
    # collector.run_collection(content_type='video', selected_categories=['MBN종합뉴스', '뉴스파이터'])


if __name__ == "__main__":
    main()
