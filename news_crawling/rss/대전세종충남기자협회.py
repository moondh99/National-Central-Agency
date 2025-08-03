#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DJ저널리스트(대전세종충남기자협회) RSS 수집기
Created: 2025년 8월
Description: DJ저널리스트(www.djjournalist.or.kr)의 RSS 피드를 수집하여 CSV 파일로 저장
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


class DJJournalistRSSCollector:
    def __init__(self):
        self.base_url = "http://www.djjournalist.or.kr"  # HTTP 프로토콜 사용
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]

        # DJ저널리스트 RSS 피드 카테고리 (이미지에서 확인한 정확한 구조)
        self.rss_categories = {
            "전체기사": "allArticle.xml",
            "인기기사": "clickTop.xml",
            "지회소식": "S1N1.xml",
            "외부기고": "S1N2.xml",
            "회원소식": "S1N3.xml",
            "사진": "S1N4.xml",
            "협회장인사말": "S1N5.xml",
            "기업소개": "S1N6.xml",
            "협회원소식": "S1N7.xml",
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
        # DJ저널리스트 특화: 불필요한 패턴 제거
        text = re.sub(r"\]\]>", "", text)
        text = re.sub(r"대전세종충남기자협회\s*", "", text)

        return text.strip()

    def extract_reporter_name(self, article_url):
        """기사 URL에서 기자명 추출"""
        try:
            headers = {"User-Agent": self.get_random_user_agent()}
            response = self.session.get(article_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # DJ저널리스트 기자명 패턴 찾기
            reporter_patterns = [
                # 기사 본문 끝 기자명 패턴: "서혜영 기자"
                r"([가-힣]{2,4})\s*기자",
                # 이메일과 함께: "김진호기자 kimjh@example.com"
                r"([가-힣]{2,4})기자\s+[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                # 태그 내 기자명
                r'<[^>]*class="reporter"[^>]*>([가-힣]{2,4})',
                # 기사 하단 기자 정보
                r"기자\s*:\s*([가-힣]{2,4})",
                r"글\s*:\s*([가-힣]{2,4})",
            ]

            article_text = soup.get_text()

            for pattern in reporter_patterns:
                match = re.search(pattern, article_text)
                if match:
                    reporter_name = match.group(1).strip()
                    # DJ저널리스트 특성: 협회 공식 글인 경우 처리
                    if reporter_name not in ["대전세종충남", "협회", "기자협회"]:
                        return reporter_name

            # DJ저널리스트 특성: RSS에서 작성자 정보 확인
            # RSS 피드에 이미 작성자 정보가 있는 경우가 많음
            if "대전세종충남기자협회" in article_text:
                return "협회공식"

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
                            # DJ저널리스트의 날짜 형식에 맞게 파싱
                            pub_date = datetime.strptime(entry.published, "%Y-%m-%d %H:%M:%S").strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        except:
                            pub_date = entry.published

                    # 요약 내용
                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self.clean_text(entry.summary)
                    elif hasattr(entry, "description"):
                        summary = self.clean_text(entry.description)

                    # 작성자 정보 (RSS에서 먼저 확인)
                    reporter = "정보수집중"
                    if hasattr(entry, "author") and entry.author:
                        reporter = self.clean_text(entry.author)
                        # '대전세종충남기자협회'인 경우 협회공식으로 처리
                        if "대전세종충남기자협회" in reporter:
                            reporter = "협회공식"
                    else:
                        # RSS에 작성자 정보가 없으면 기사에서 추출 (선택적)
                        if len(articles) < 3:  # 처음 3개 기사만 기자명 추출
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
            filename = f"results/DJ저널리스트_RSS_{timestamp}.csv"

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

        print("📰 DJ저널리스트(대전세종충남기자협회) RSS 수집기 시작")
        print("=" * 60)

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

        print("=" * 60)
        print(f"📊 총 수집 기사: {len(all_articles)}개")

        if all_articles:
            saved_file = self.save_to_csv(all_articles)
            if saved_file:
                print(f"✅ 수집 완료! 파일: {saved_file}")

        return all_articles


def main():
    """메인 실행 함수"""
    collector = DJJournalistRSSCollector()

    print("DJ저널리스트(대전세종충남기자협회) RSS 수집기")
    print("=" * 50)
    print("사용 가능한 카테고리:")
    for i, category in enumerate(collector.rss_categories.keys(), 1):
        print(f"{i:2d}. {category}")
    print("=" * 50)

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
        print(f"\n🎉 DJ저널리스트 RSS 수집이 완료되었습니다!")
        print(f"📈 총 {len(articles)}개의 기사를 수집했습니다.")
        print(f"📍 기자협회 특성: 기자들의 개인 에세이와 협회 소식이 주요 콘텐츠입니다.")
    else:
        print("\n❌ 수집된 기사가 없습니다.")


if __name__ == "__main__":
    main()
