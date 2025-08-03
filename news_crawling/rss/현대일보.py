import feedparser
import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import time
import random
import re


class HyundaiIlboRSSCollector:
    def __init__(self):
        self.base_url = "http://www.hyundaiilbo.com"
        self.rss_urls = {
            "전체기사": "http://www.hyundaiilbo.com/rss/allArticle.xml",
            "인기기사": "http://www.hyundaiilbo.com/rss/clickTop.xml",
            "뉴스": "http://www.hyundaiilbo.com/rss/S1N1.xml",
            "인천·경기": "http://www.hyundaiilbo.com/rss/S1N2.xml",
            "오피니언": "http://www.hyundaiilbo.com/rss/S1N3.xml",
            "사람들": "http://www.hyundaiilbo.com/rss/S1N4.xml",
            "포토뉴스": "http://www.hyundaiilbo.com/rss/S1N5.xml",
        }

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]

        self.session = requests.Session()

    def get_random_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def extract_reporter_name(self, content):
        """기자명 추출"""
        if not content:
            return ""

        # 현대일보 기자명 패턴들
        patterns = [
            r"([가-힣]{2,4})\s*기자",
            r"기자\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*논설위원",
            r"([가-힣]{2,4})\s*편집위원",
            r"■\s*([가-힣]{2,4})",
            r"▲\s*([가-힣]{2,4})",
            r"△\s*([가-힣]{2,4})",
            r"([가-힣]{2,4})\s*@",
            r"([가-힣]{2,4})\s*\w+@\w+\.\w+",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                name = match.group(1).strip()
                if len(name) >= 2 and name not in ["기자", "특파원", "위원", "논설", "편집"]:
                    return name

        return ""

    def clean_content(self, content):
        """본문 내용 정제"""
        if not content:
            return ""

        # HTML 태그 제거
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text()

        # 불필요한 내용 제거
        remove_patterns = [
            r"저작권자\s*©\s*현대일보.*?금지",
            r"무단전재.*?재배포.*?금지",
            r"Copyright.*?All rights reserved",
            r"계정을 선택하시면.*?댓글을 남기실 수 있습니다\.",
            r"로그인·계정인증을 통해.*?댓글을",
            r"\[현대일보\]",
            r"현대일보\s*=",
            r"▲.*?=",
            r"■.*?=",
            r"△.*?=",
            r"\s+",
            r"^\s*\n",
            r"\n\s*$",
        ]

        for pattern in remove_patterns:
            text = re.sub(pattern, " ", text, flags=re.MULTILINE | re.DOTALL)

        # 연속된 공백과 줄바꿈 정리
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def get_article_content(self, article_url):
        """개별 기사 본문 가져오기"""
        try:
            headers = self.get_random_headers()
            response = self.session.get(article_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 기사 본문 추출 (현대일보 구조에 맞춘 선택자)
            content_selectors = [
                "div.news-content",
                "div.article-content",
                "div.view-content",
                "div#article-view-content-div",
                "div.user-content",
                "div.article_txt",
                "div.content",
            ]

            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text()
                    break

            # 본문이 없으면 전체에서 추출 시도
            if not content:
                # 스크립트, 스타일, 네비게이션 등 제거
                for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    element.decompose()

                content = soup.get_text()

            return self.clean_content(content)

        except Exception as e:
            print(f"본문 추출 오류 ({article_url}): {e}")
            return ""

    def collect_rss_data(self, category=None, max_articles=50):
        """RSS 데이터 수집"""
        collected_data = []

        # 특정 카테고리만 수집하거나 전체 수집
        urls_to_process = {}
        if category and category in self.rss_urls:
            urls_to_process[category] = self.rss_urls[category]
        else:
            urls_to_process = self.rss_urls

        for category_name, rss_url in urls_to_process.items():
            print(f"\n=== {category_name} RSS 수집 시작 ===")

            try:
                # RSS 피드 파싱
                feed = feedparser.parse(rss_url)

                if not feed.entries:
                    print(f"❌ {category_name}: RSS 피드가 비어있습니다.")
                    continue

                print(f"📰 {category_name}: {len(feed.entries)}개 기사 발견")

                # 각 기사 처리
                for i, entry in enumerate(feed.entries[:max_articles]):
                    try:
                        print(f"처리 중... {i+1}/{min(len(feed.entries), max_articles)}: {entry.title[:50]}...")

                        # 기본 정보 추출
                        title = entry.title if hasattr(entry, "title") else ""
                        link = entry.link if hasattr(entry, "link") else ""

                        # 발행일 처리
                        pub_date = ""
                        if hasattr(entry, "published"):
                            try:
                                pub_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                pub_date = entry.published

                        # 기사 본문 가져오기
                        content = ""
                        reporter = ""
                        if link:
                            content = self.get_article_content(link)
                            reporter = self.extract_reporter_name(content)

                        # 요약 정보 (RSS에서 제공되는 경우)
                        summary = ""
                        if hasattr(entry, "summary"):
                            summary = BeautifulSoup(entry.summary, "html.parser").get_text()

                        # 데이터 저장
                        article_data = {
                            "category": category_name,
                            "title": title,
                            "link": link,
                            "pub_date": pub_date,
                            "reporter": reporter,
                            "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                            "content": content[:1000] + "..." if len(content) > 1000 else content,
                            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }

                        collected_data.append(article_data)

                        # 요청 간격 조절
                        time.sleep(random.uniform(0.5, 1.5))

                    except Exception as e:
                        print(f"❌ 기사 처리 오류: {e}")
                        continue

                print(
                    f"✅ {category_name}: {len([d for d in collected_data if d['category'] == category_name])}개 기사 수집 완료"
                )

            except Exception as e:
                print(f"❌ {category_name} RSS 수집 실패: {e}")
                continue

        return collected_data

    def save_to_csv(self, data, filename=None):
        """CSV 파일로 저장"""
        if not data:
            print("저장할 데이터가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/hyundaiilbo_news_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["category", "title", "link", "pub_date", "reporter", "summary", "content", "collected_at"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            print(f"\n✅ 데이터 저장 완료: {filename}")
            print(f"📊 총 {len(data)}개 기사 저장")

            # 카테고리별 통계
            category_stats = {}
            for item in data:
                cat = item["category"]
                category_stats[cat] = category_stats.get(cat, 0) + 1

            print("\n📈 카테고리별 수집 현황:")
            for cat, count in category_stats.items():
                print(f"  - {cat}: {count}개")

        except Exception as e:
            print(f"❌ CSV 저장 실패: {e}")


def main():
    print("🏛️ 현대일보 RSS 수집기 시작")
    print("=" * 50)

    collector = HyundaiIlboRSSCollector()

    # 사용 예시
    print("📋 수집 가능한 카테고리:")
    for i, category in enumerate(collector.rss_urls.keys(), 1):
        print(f"  {i}. {category}")

    print("\n🚀 전체 카테고리 수집을 시작합니다...")

    # 전체 카테고리에서 각각 30개씩 수집
    collected_data = collector.collect_rss_data(max_articles=30)

    # CSV 저장
    if collected_data:
        collector.save_to_csv(collected_data)
        print(f"\n🎉 수집 완료! 총 {len(collected_data)}개 기사를 수집했습니다.")
    else:
        print("\n❌ 수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
