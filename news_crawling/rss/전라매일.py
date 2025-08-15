import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re
import urllib.parse


class JlmaeilRSSCollector:
    def __init__(self):
        # 정확한 도메인 확인됨
        self.base_url = "http://www.jlmaeil.com"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

        # 전라매일 RSS 피드 카테고리 (이미지와 검색결과에서 확인한 정확한 구조)
        self.rss_categories = {
            "전체기사": None,  # 기본 RSS (http://www.jlmaeil.com/rss/rss.php)
            "영상": 230,
            "e-전라매일영상": 231,
            "정치": 176,
            "정치군정": 177,
            "사회": 178,
            "사회일반": 179,
            "사건사고": 180,
            "경제IT": 181,
            "경제": 182,
            "문화": 184,
            "문화공연": 186,
            "축제행사": 187,
            "생활스포츠": 188,
            "연예": 189,
            "교육1": 244,
            "교육2": 245,
            "행복을여는사람들": 190,
            "행복한기사": 191,
            "사설칼럼": 192,
            "사설": 193,
            "칼럼": 194,
            "오피니언": 197,
            "독자기고": 198,
            "독자투고": 199,
            "기자수첩": 243,
            "기획": 200,
            "기획특집": 201,
        }

        self.session = requests.Session()

    def get_random_user_agent(self):
        """랜덤 User-Agent 반환"""
        return random.choice(self.user_agents)

    def clean_text(self, text):
        """텍스트 정제"""
        if not text:
            return ""

        # HTML 태그 제거
        text = re.sub(r"<[^>]+>", "", text)
        # 특수문자 정제
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        # 따옴표 처리
        text = text.replace('"', '""')

        return text.strip()

    def extract_reporter_name(self, article_url):
        """기사 URL에서 기자명 추출"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(article_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # 전라매일 기자명 패턴 찾기
            reporter_patterns = [
                # 기본 기자명 패턴
                r"([가-힣]{2,4})\s*기자",
                # 이메일과 함께
                r"([가-힣]{2,4})기자\s+[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                # 태그 내 기자명
                r'<[^>]*class="reporter"[^>]*>([가-힣]{2,4})',
                r'<[^>]*class="writer"[^>]*>([가-힣]{2,4})',
                # 기사 정보 영역
                r"기자\s*[:：]\s*([가-힣]{2,4})",
                r"글\s*[:：]\s*([가-힣]{2,4})",
                r"취재\s*[:：]\s*([가-힣]{2,4})",
                # 기사 하단 서명
                r"([가-힣]{2,4})\s*기자\s*[／/]\s*",
                r"／([가-힣]{2,4})\s*기자",
            ]

            article_text = soup.get_text()

            for pattern in reporter_patterns:
                matches = re.findall(pattern, article_text, re.MULTILINE)
                if matches:
                    # 가장 마지막에 나오는 기자명이 실제 기자명일 확률이 높음
                    reporter_name = matches[-1].strip()
                    if len(reporter_name) >= 2 and not re.search(r"[0-9]", reporter_name):
                        return reporter_name

        except Exception as e:
            print(f"기자명 추출 오류 ({article_url}): {e}")

        return "정보없음"

    def extract_article_content(self, article_url):
        """기사 본문 추출"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(article_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            # 본문 영역 추출 (style 속성 기반)
            content_div = soup.find("div", style=lambda v: v and "padding:0 20px" in v)
            if content_div:
                return self.clean_text(content_div.get_text(separator="\n"))
        except Exception as e:
            print(f"본문 추출 오류 ({article_url}): {e}")
        return ""

    def collect_rss_feed(self, category_name, part_idx):
        """특정 카테고리의 RSS 피드 수집"""
        # 전체기사 RSS URL 고정
        rss_url = f"{self.base_url}/rss/rss.php"
        print(f"{category_name} 카테고리 자동 수집 중: {rss_url}")
        headers = {"User-Agent": self.get_random_user_agent()}
        resp = self.session.get(rss_url, headers=headers, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        entries = feed.entries[:20]
        articles = []
        for entry in entries:
            title = self.clean_text(entry.title)
            link = entry.link
            # 날짜
            pub_date = getattr(entry, "published", getattr(entry, "updated", ""))
            # 카테고리 (RSS 태그)
            category = getattr(entry, "category", entry.tags[0].term if entry.tags else "")
            # 기자명
            reporter = self.clean_text(entry.author) if hasattr(entry, "author") else "정보없음"
            # 본문
            content = self.extract_article_content(link)
            articles.append(
                {
                    "언론사": "전라매일",
                    "제목": title,
                    "날짜": pub_date,
                    "카테고리": category,
                    "기자명": reporter,
                    "본문": content,
                }
            )
            time.sleep(random.uniform(0.5, 1.0))
        return articles

    def save_to_csv(self, all_articles, filename=None):
        """수집된 기사들을 CSV 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"results/전라매일_전체_{timestamp}.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
            fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for art in all_articles:
                writer.writerow(art)
        print(f"📄 CSV 파일 저장 완료: {filename}")
        return filename

    def test_connection(self):
        """도메인 연결 테스트"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(f"{self.base_url}/rss/", headers=headers, timeout=10)
            print(f"✅ 도메인 연결 성공: {self.base_url}")
            return True
        except Exception as e:
            print(f"❌ 도메인 연결 실패: {e}")
            print("⚠️  도메인 주소를 확인해주세요.")
            return False

    def collect_all_categories(self, selected_categories=None):
        """모든 카테고리 또는 선택된 카테고리의 RSS 수집"""
        if selected_categories is None:
            selected_categories = list(self.rss_categories.keys())

        print("📰 전라매일 RSS 수집기 시작")
        print("=" * 50)

        # 도메인 연결 테스트
        print("🔍 도메인 연결 상태 확인 중...")
        if not self.test_connection():
            print("❌ 도메인 연결에 실패했습니다.")
            print("💡 네트워크 연결이나 도메인 주소를 확인해주세요.")
            return []

        all_articles = []

        for category in selected_categories:
            if category in self.rss_categories:
                part_idx = self.rss_categories[category]
                articles = self.collect_rss_feed(category, part_idx)
                all_articles.extend(articles)

                # 요청 간격 (서버 부하 방지)
                time.sleep(random.uniform(1.0, 2.0))
            else:
                print(f"⚠️  알 수 없는 카테고리: {category}")

        print("=" * 50)
        print(f"📊 총 수집 기사: {len(all_articles)}개")

        if all_articles:
            saved_file = self.save_to_csv(all_articles)
            if saved_file:
                print(f"✅ 수집 완료! 파일: {saved_file}")

        return all_articles


def main():
    """메인 실행 함수"""
    collector = JlmaeilRSSCollector()
    articles = collector.collect_rss_feed("전체기사", None)
    if articles:
        saved = collector.save_to_csv(articles)
        print(f"✅ 전라매일 전체기사 {len(articles)}개 수집 완료, 파일: {saved}")
    else:
        print("❌ 수집된 기사가 없습니다.")


if __name__ == "__main__":
    main()
