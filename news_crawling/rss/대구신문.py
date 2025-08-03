#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
대구신문 RSS 수집기
Created: 2025년 8월
Description: 대구신문(www.idaegu.co.kr)의 RSS 피드를 수집하여 CSV 파일로 저장
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import re
import urllib.parse


class DaeguShinmunRSSCollector:
    def __init__(self):
        self.base_url = "https://www.idaegu.co.kr"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

        # 대구신문 RSS 피드 카테고리
        self.rss_categories = {
            "전체기사": "allArticle.xml",
            "인기기사": "clickTop.xml",
            "정치": "S1N1.xml",
            "경제": "S1N2.xml",
            "사회": "S1N3.xml",
            "경북": "S1N4.xml",
            "문화": "S1N5.xml",
            "스포츠": "S1N6.xml",
            "오피니언": "S1N7.xml",
            "포토뉴스": "S1N8.xml",
            "사람들": "S1N9.xml",
            "여러이는미래다": "S1N10.xml",
            "독자마당": "S1N11.xml",
            "기획특집": "S1N12.xml",
            "종합": "S1N13.xml",
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

            # 대구신문 기자명 패턴 찾기
            reporter_patterns = [
                # 기사 본문 끝 기자명 패턴: "김진오기자 kimjo@idaegu.co.kr"
                r"([가-힣]{2,4})기자\s+[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                # 기자명만: "김진오"
                r"([가-힣]{2,4})기자",
                # 기사 내 기자명 태그
                r'<[^>]*class="reporter"[^>]*>([가-힣]{2,4})',
                r"<[^>]*기자[^>]*>([가-힣]{2,4})",
            ]

            article_text = soup.get_text()

            for pattern in reporter_patterns:
                match = re.search(pattern, article_text)
                if match:
                    return match.group(1).strip()

            # 추가 패턴: 기사 내용에서 "○○○기자" 형태 찾기
            reporter_match = re.search(r"([가-힣]{2,4})기자(?:\s|$)", article_text)
            if reporter_match:
                return reporter_match.group(1)

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

            for entry in feed.entries:
                try:
                    # 기본 정보 추출
                    title = self.clean_text(entry.title)
                    link = entry.link

                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, "published"):
                        try:
                            pub_date = datetime.strptime(entry.published, "%Y-%m-%d %H:%M:%S").strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        except:
                            pub_date = entry.published

                    # 요약 내용
                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self.clean_text(entry.summary)

                    # 기자명 추출 (속도를 위해 선택적으로 실행)
                    reporter = "정보수집중"
                    if len(articles) < 5:  # 처음 5개 기사만 기자명 추출
                        reporter = self.extract_reporter_name(link)
                        time.sleep(random.uniform(0.5, 1.0))  # 요청 간격

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
            filename = f"results/대구신문_RSS_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = ["category", "title", "link", "published", "summary", "reporter", "collected_at"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in all_articles:
                    writer.writerow(article)

            print(f"📄 CSV 파일 저장 완료: {filename}")
            return filename

        except Exception as e:
            print(f"❌ CSV 저장 실패: {e}")
            return None

    def collect_all_categories(self, selected_categories=None):
        """모든 카테고리 또는 선택된 카테고리의 RSS 수집"""
        if selected_categories is None:
            selected_categories = list(self.rss_categories.keys())

        print("🗞️  대구신문 RSS 수집기 시작")
        print("=" * 50)

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
    collector = DaeguShinmunRSSCollector()

    print("대구신문 RSS 수집기")
    print("=" * 30)
    print("사용 가능한 카테고리:")
    for i, category in enumerate(collector.rss_categories.keys(), 1):
        print(f"{i:2d}. {category}")
    print("=" * 30)

    # 사용자 선택
    choice = input("\n수집할 카테고리를 선택하세요 (번호 입력, 전체는 'all'): ").strip()

    if choice.lower() == "all":
        selected_categories = list(collector.rss_categories.keys())
        print("🔄 모든 카테고리를 수집합니다.")
    else:
        try:
            if "," in choice:
                # 여러 카테고리 선택
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected_categories = [
                    list(collector.rss_categories.keys())[i] for i in indices if 0 <= i < len(collector.rss_categories)
                ]
            else:
                # 단일 카테고리 선택
                index = int(choice) - 1
                if 0 <= index < len(collector.rss_categories):
                    selected_categories = [list(collector.rss_categories.keys())[index]]
                else:
                    print("❌ 잘못된 번호입니다.")
                    return
        except ValueError:
            print("❌ 올바른 번호를 입력해주세요.")
            return

    # RSS 수집 실행
    articles = collector.collect_all_categories(selected_categories)

    if articles:
        print(f"\n🎉 대구신문 RSS 수집이 완료되었습니다!")
        print(f"📈 총 {len(articles)}개의 기사를 수집했습니다.")
    else:
        print("\n❌ 수집된 기사가 없습니다.")


if __name__ == "__main__":
    main()
