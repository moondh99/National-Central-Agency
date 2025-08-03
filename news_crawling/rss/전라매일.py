#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
전라매일 RSS 수집기
Created: 2025년 8월
Description: 전라매일(www.jlmaeil.com)의 RSS 피드를 수집하여 CSV 파일로 저장
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

    def collect_rss_feed(self, category_name, part_idx):
        """특정 카테고리의 RSS 피드 수집"""
        if part_idx is None:
            # 전체기사의 경우 기본 RSS 주소
            rss_url = f"{self.base_url}/rss/rss.php"
        else:
            rss_url = f"{self.base_url}/rss/rss.php?part_idx={part_idx}"

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
                            # 다양한 날짜 형식 시도
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

                    # 작성자 정보 (RSS에서 먼저 확인)
                    reporter = "정보수집중"
                    if hasattr(entry, "author") and entry.author:
                        reporter = self.clean_text(entry.author)
                    else:
                        # RSS에 작성자 정보가 없으면 기사에서 추출 (선택적)
                        if len(articles) < 3:  # 처음 3개 기사만 기자명 추출
                            reporter = self.extract_reporter_name(link)
                            time.sleep(random.uniform(0.5, 1.0))  # 요청 간격

                    article_data = {
                        "category": category_name,
                        "part_idx": part_idx if part_idx else "default",
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
            filename = f"results/전라매일_RSS_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                fieldnames = [
                    "category",
                    "part_idx",
                    "title",
                    "link",
                    "published",
                    "summary",
                    "reporter",
                    "collected_at",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in all_articles:
                    writer.writerow(article)

            print(f"📄 CSV 파일 저장 완료: {filename}")
            return filename

        except Exception as e:
            print(f"❌ CSV 저장 실패: {e}")
            return None

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

    print("📰 전라매일 RSS 수집기")
    print("=" * 50)
    print("사용 가능한 카테고리:")
    for i, (category, part_idx) in enumerate(collector.rss_categories.items(), 1):
        idx_info = f"(idx: {part_idx})" if part_idx else "(기본)"
        print(f"{i:2d}. {category:15s} {idx_info}")
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
                print(f"🔄 선택된 카테고리: {', '.join(selected_categories)}")
            else:
                # 단일 카테고리 선택
                index = int(choice) - 1
                if 0 <= index < len(collector.rss_categories):
                    selected_categories = [list(collector.rss_categories.keys())[index]]
                    print(f"🔄 선택된 카테고리: {selected_categories[0]}")
                else:
                    print("❌ 잘못된 번호입니다.")
                    return
        except ValueError:
            print("❌ 올바른 번호를 입력해주세요.")
            return

    # RSS 수집 실행
    articles = collector.collect_all_categories(selected_categories)

    if articles:
        print(f"\n🎉 전라매일 RSS 수집이 완료되었습니다!")
        print(f"📈 총 {len(articles)}개의 기사를 수집했습니다.")
        print(f"📍 지역언론 특성: 전라남도 지역 뉴스와 다양한 분야별 기사")
    else:
        print("\n❌ 수집된 기사가 없습니다.")
        print("💡 도메인 주소나 네트워크 연결을 확인해주세요.")


if __name__ == "__main__":
    main()
