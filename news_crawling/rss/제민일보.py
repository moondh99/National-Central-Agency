import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re
import urllib.parse


class JeminRSSCollector:
    def __init__(self):
        self.base_url = "https://www.jemin.com"  # HTTPS 프로토콜 사용
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

        # 제민일보 RSS 피드 카테고리 (이미지에서 확인한 정확한 구조)
        self.rss_categories = {
            "전체기사": "allArticle.xml",
            "제민방송": "S1N1.xml",
            "정치": "S1N2.xml",
            "경제": "S1N3.xml",
            "사회": "S1N4.xml",
            "교육": "S1N5.xml",
            "기획": "S1N7.xml",
            "오피니언": "S1N8.xml",
            "문화": "S1N9.xml",
            "지역뉴스": "S1N16.xml",
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

            # 제민일보 기자명 패턴 찾기
            reporter_patterns = [
                # 기본 기자명 패턴: "김두영 기자"
                r"([가-힣]{2,4})\s*기자",
                # 이메일과 함께: "김두영기자 kdy@jemin.com"
                r"([가-힣]{2,4})기자\s+[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                # 태그 내 기자명
                r'<[^>]*class="reporter"[^>]*>([가-힣]{2,4})',
                r'<[^>]*class="writer"[^>]*>([가-힣]{2,4})',
                # 기사 정보 영역
                r"기자명\s*[:：]\s*([가-힣]{2,4})",
                r"글\s*[:：]\s*([가-힣]{2,4})",
                r"취재\s*[:：]\s*([가-힣]{2,4})",
                # 제민일보 특성: 기사 하단 기자명
                r"([가-힣]{2,4})\s*기자\s*$",
                r"저작권자.*제민일보.*무단전재.*([가-힣]{2,4})\s*기자",
                # 지역=기자명 패턴 (제주 지역 기자 특성)
                r"([가-힣]{2,8})=([가-힣]{2,4})\s*기자",
            ]

            article_text = soup.get_text()

            for pattern in reporter_patterns:
                if "=" in pattern:  # 지역=기자명 패턴
                    matches = re.findall(r"([가-힣]{2,8})=([가-힣]{2,4})\s*기자", article_text)
                    if matches:
                        # 지역명=기자명 에서 기자명만 추출
                        return matches[-1][1].strip()
                else:
                    matches = re.findall(pattern, article_text, re.MULTILINE)
                    if matches:
                        reporter_name = matches[-1].strip()
                        if len(reporter_name) >= 2 and not re.search(r"[0-9]", reporter_name):
                            # 제민일보 특성: 특정 단어 제외
                            if reporter_name not in ["제민일보", "저작권자", "무단전재", "재배포", "기자명"]:
                                return reporter_name

        except Exception as e:
            print(f"기자명 추출 오류 ({article_url}): {e}")

        return "정보없음"

    def collect_rss_feed(self, category_name, rss_file):
        """특정 카테고리의 RSS 피드 수집"""
        rss_url = f"{self.base_url}/rss/{rss_file}"

        try:
            print(f"{category_name} 카테고리 수집 중: {rss_url}")

            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(rss_url, headers=headers, timeout=15)
            response.raise_for_status()

            # RSS 파싱
            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"❌ {category_name}: RSS 항목이 없습니다.")
                return []

            articles = []

            for entry in feed.entries[:20]:
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.title)
                    link = entry.link

                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, "published"):
                        try:
                            # 제민일보의 날짜 형식 처리
                            from dateutil import parser

                            parsed_date = parser.parse(entry.published)
                            pub_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pub_date = entry.published
                    elif hasattr(entry, "updated"):
                        try:
                            from dateutil import parser

                            parsed_date = parser.parse(entry.updated)
                            pub_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pub_date = entry.updated

                    # 요약 내용
                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self.clean_text(entry.summary)
                    elif hasattr(entry, "description"):
                        summary = self.clean_text(entry.description)

                    # 본문 추출 (원문 페이지에서)
                    try:
                        page_resp = self.session.get(link, headers=headers, timeout=10)
                        page_resp.raise_for_status()
                        page_soup = BeautifulSoup(page_resp.content, "html.parser")
                        article_div = page_soup.find("article", id="article-view-content-div")
                        if article_div:
                            paragraphs = article_div.find_all("p")
                            full_texts = [self.clean_text(p.get_text()) for p in paragraphs]
                            summary = "\n".join(full_texts)
                    except Exception:
                        pass

                    # 작성자 정보: RSS author 사용, 없으면 정보없음
                    if hasattr(entry, "author") and entry.author:
                        reporter = self.clean_text(entry.author).replace(" 기자", "")
                    else:
                        reporter = "정보없음"

                    article_data = {
                        "category": category_name,
                        "title": title,
                        "link": link,
                        "published": pub_date,
                        "summary": summary,
                        "reporter": reporter,
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    articles.append(article_data)

                except Exception as e:
                    print(f"기사 처리 오류: {e}")
                    continue

            print(f"✅ {category_name}: {len(articles)}개 기사 수집 완료")
            return articles

        except Exception as e:
            print(f"❌ {category_name} RSS 수집 실패: {e}")
            return []

    def save_to_csv(self, all_articles, filename=None):
        """수집된 기사들을 CSV 파일로 저장"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/제민일보_전체_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in all_articles:
                    row = {
                        "언론사": "제민일보",
                        "제목": article.get("title", ""),
                        "날짜": article.get("published", ""),
                        "카테고리": article.get("category", ""),
                        "기자명": article.get("reporter", ""),
                        "본문": article.get("summary", ""),
                    }
                    writer.writerow(row)

            print(f"📄 CSV 파일 저장 완료: {filename}")
            return filename

        except Exception as e:
            print(f"❌ CSV 저장 실패: {e}")
            return None

    def test_connection(self):
        """도메인 연결 테스트"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(f"{self.base_url}/rss/allArticle.xml", headers=headers, timeout=10)
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

        print("📰 제민일보 RSS 수집기 시작")
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
                rss_file = self.rss_categories[category]
                articles = self.collect_rss_feed(category, rss_file)
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
    collector = JeminRSSCollector()
    print("📰 제민일보 RSS 자동 수집기 (각 카테고리 20개씩)")
    articles = collector.collect_all_categories()
    if articles:
        print(f"\n🎉 제민일보 RSS 수집이 완료되었습니다! 총 {len(articles)}개의 기사를 수집했습니다.")


if __name__ == "__main__":
    main()
