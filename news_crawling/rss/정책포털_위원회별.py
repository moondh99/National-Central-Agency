import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import time
import random
import re
from datetime import datetime
import csv
from urllib.parse import urljoin, urlparse
import logging
import os


class KoreaCommitteeRSSCrawler:
    def __init__(self):
        """정책브리핑 정부 위원회별 RSS 크롤러 초기화"""
        self.base_url = "https://www.korea.kr"

        # 6개 정부 위원회 RSS 피드
        self.committee_feeds = {
            "방송통신위원회": "https://www.korea.kr/rss/dept_kcc.xml",
            "원자력안전위원회": "https://www.korea.kr/rss/dept_nssc.xml",
            "공정거래위원회": "https://www.korea.kr/rss/dept_ftc.xml",
            "금융위원회": "https://www.korea.kr/rss/dept_fsc.xml",
            "국민권익위원회": "https://www.korea.kr/rss/dept_acrc.xml",
            "개인정보보호위원회": "https://www.korea.kr/rss/dept_pipc.xml",
        }

        # 위원회별 주요 업무 분야 (분석용)
        self.committee_areas = {
            "방송통신위원회": "방송정책, 통신정책, 미디어규제, 인터넷정책",
            "원자력안전위원회": "원자력안전, 방사능방재, 원전안전규제",
            "공정거래위원회": "공정거래, 독점규제, 소비자보호, 경쟁정책",
            "금융위원회": "금융정책, 금융감독, 자본시장, 금융소비자보호",
            "국민권익위원회": "부패방지, 국민신문고, 행정심판, 갈등조정",
            "개인정보보호위원회": "개인정보보호, 프라이버시정책, 정보보안",
        }

        # 위원회 카테고리 분류
        self.committee_categories = {
            "방송·통신": ["방송통신위원회"],
            "원자력·안전": ["원자력안전위원회"],
            "경제·공정거래": ["공정거래위원회", "금융위원회"],
            "권익·정보보호": ["국민권익위원회", "개인정보보호위원회"],
        }

        # 위원회별 주요 키워드
        self.committee_keywords = {
            "방송통신위원회": ["방송", "통신", "미디어", "ICT", "인터넷", "방송법", "통신법", "플랫폼"],
            "원자력안전위원회": ["원자력", "원전", "방사능", "안전규제", "핵안전", "방사선"],
            "공정거래위원회": ["공정거래", "독점", "담합", "소비자", "경쟁", "카르텔", "시장지배력"],
            "금융위원회": ["금융", "은행", "증권", "보험", "자본시장", "금융소비자", "핀테크"],
            "국민권익위원회": ["부패방지", "신문고", "행정심판", "갈등조정", "공익신고", "옴부즈만"],
            "개인정보보호위원회": ["개인정보", "프라이버시", "정보보호", "GDPR", "데이터", "동의"],
        }

        # User-Agent 리스트
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]

        self.articles = []
        self.session = requests.Session()

        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 헤더 생성"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def random_delay(self, min_delay=1, max_delay=3):
        """랜덤 딜레이"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    def fetch_rss_feed(self, rss_url, max_retries=3):
        """RSS 피드 가져오기"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(rss_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except Exception as e:
                self.logger.warning(f"RSS 피드 가져오기 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(2, 5)
                else:
                    self.logger.error(f"RSS 피드 가져오기 최종 실패: {rss_url}")
                    return None

    def parse_rss_feed(self, rss_content):
        """RSS 피드 파싱"""
        try:
            root = ET.fromstring(rss_content)
            items = []

            for item in root.findall(".//item"):
                article_info = {}

                # 기본 정보 추출
                title_elem = item.find("title")
                article_info["title"] = title_elem.text.strip() if title_elem is not None else ""

                link_elem = item.find("link")
                article_info["link"] = link_elem.text.strip() if link_elem is not None else ""

                pubdate_elem = item.find("pubDate")
                article_info["pub_date"] = pubdate_elem.text.strip() if pubdate_elem is not None else ""

                guid_elem = item.find("guid")
                article_info["guid"] = guid_elem.text.strip() if guid_elem is not None else ""

                # dc:creator 추출 (네임스페이스 고려)
                creator_elem = item.find(".//{http://purl.org/dc/elements/1.1/}creator")
                article_info["creator"] = creator_elem.text.strip() if creator_elem is not None else ""

                # description에서 전체 내용 추출
                desc_elem = item.find("description")
                if desc_elem is not None:
                    desc_text = desc_elem.text or ""
                    # CDATA 처리
                    if desc_text.startswith("<![CDATA[") and desc_text.endswith("]]>"):
                        desc_text = desc_text[9:-3]
                    # HTML 태그 제거하여 텍스트만 추출
                    soup = BeautifulSoup(desc_text, "html.parser")
                    article_info["description"] = soup.get_text().strip()
                else:
                    article_info["description"] = ""

                items.append(article_info)

            return items
        except Exception as e:
            self.logger.error(f"RSS 파싱 오류: {e}")
            return []

    def extract_article_content(self, article_url, max_retries=3):
        """개별 기사 본문 추출 - 위원회 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"

                soup = BeautifulSoup(response.text, "html.parser")

                # 위원회별 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    ".committee_cont",  # 위원회 콘텐츠
                    ".press_cont",  # 보도자료 콘텐츠
                    ".decision_cont",  # 의결사항 콘텐츠
                    ".article_body",  # 일반 기사
                    ".rbody",  # 브리핑 페이지
                    ".view_cont",  # 뷰 페이지
                    ".cont_body",  # 콘텐츠 본문
                    ".policy_body",  # 정책 본문
                    ".briefing_cont",  # 브리핑 내용
                    ".news_cont",  # 뉴스 내용
                    ".notice_cont",  # 공지사항 내용
                    ".regulation_cont",  # 규제 내용
                ]

                content = ""
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        content = content_elem.get_text().strip()
                        break

                # 본문이 없으면 전체 텍스트에서 추출 시도
                if not content:
                    # 헤더, 푸터, 사이드바 등 제거
                    for elem in soup.find_all(["header", "footer", "nav", "aside", "script", "style"]):
                        elem.decompose()

                    main_content = soup.find("main") or soup.find("div", class_="content") or soup.find("body")
                    if main_content:
                        content = main_content.get_text().strip()

                # 위원회별 특화 정보 추출
                contact_info = self.extract_committee_contact_info(content)
                regulation_keywords = self.extract_regulation_keywords(content)
                decision_type = self.extract_decision_type(content)

                # 텍스트 정리
                content = re.sub(r"\s+", " ", content).strip()

                return {
                    "content": content[:3500] + "..." if len(content) > 3500 else content,
                    "contact_info": contact_info,
                    "regulation_keywords": regulation_keywords,
                    "decision_type": decision_type,
                }

            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {"content": "추출 실패", "contact_info": "", "regulation_keywords": "", "decision_type": ""}

    def extract_committee_contact_info(self, content):
        """위원회 연락처/담당자 정보 추출"""
        # 위원회별 연락처 정보 추출 패턴
        patterns = [
            r"문의\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"연락처\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"문의처\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당부서\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당자\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"위원회\s+([가-힣]+과|[가-힣]+팀|[가-힣]+국)\s*(?:\(([^)]+)\))?",
            r"홈페이지\s*:\s*(https?://[^\s]+)",
        ]

        contact_info = {}

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) >= 2:
                        dept = match[0].strip() if match[0] else ""
                        contact = match[1].strip() if match[1] else ""

                        if dept and len(dept) > 1 and len(dept) < 100:
                            contact_info["department"] = dept
                        if contact:
                            if "http" in contact:
                                contact_info["website"] = contact
                            elif any(prefix in contact for prefix in ["02-", "044-", "070-"]):
                                contact_info["phone"] = contact
                else:
                    if match and len(match) > 1 and len(match) < 100:
                        contact_info["department"] = match.strip()

        return "; ".join([f"{k}: {v}" for k, v in contact_info.items()])

    def extract_regulation_keywords(self, content):
        """규제/정책 키워드 추출"""
        # 위원회별 규제/정책 키워드 패턴
        regulation_patterns = [
            r"(규제|제재|처분|조치|명령|권고|개선|시정)",
            r"(심의|의결|결정|승인|허가|인가|등록)",
            r"(법률|법령|규정|기준|가이드라인|지침)",
            r"(조사|점검|감사|감독|모니터링|평가)",
            r"(과징금|과태료|경고|주의|시정명령)",
            r"(공청회|간담회|토론회|설명회|의견수렴)",
            r"(개정|제정|폐지|신설|강화|완화)",
        ]

        keywords = set()
        for pattern in regulation_patterns:
            matches = re.findall(pattern, content)
            keywords.update(matches)

        return ", ".join(list(keywords)[:12])  # 최대 12개 키워드

    def extract_decision_type(self, content):
        """의결/결정 유형 추출"""
        decision_patterns = [
            r"(보도자료|언론배포|발표)",
            r"(의결|결정|승인)",
            r"(고시|공고|공시)",
            r"(규칙|고시|훈령)",
            r"(정책|제도|방안)",
            r"(조사결과|감사결과|점검결과)",
        ]

        for pattern in decision_patterns:
            if re.search(pattern, content):
                matches = re.findall(pattern, content)
                if matches:
                    return matches[0]

        return ""

    def get_committee_category(self, committee_name):
        """위원회의 카테고리 반환"""
        for category, committees in self.committee_categories.items():
            if committee_name in committees:
                return category
        return "기타"

    def get_relevant_keywords(self, committee_name, content):
        """위원회별 관련 키워드 매칭"""
        if committee_name in self.committee_keywords:
            keywords = self.committee_keywords[committee_name]
            found_keywords = []
            for keyword in keywords:
                if keyword in content:
                    found_keywords.append(keyword)
            return ", ".join(found_keywords[:8])  # 최대 8개
        return ""

    def crawl_committee_feed(self, committee, rss_url, max_items=30):
        """개별 위원회 RSS 피드 크롤링"""
        self.logger.info(f"위원회 크롤링 시작: {committee}")

        # RSS 피드 가져오기
        rss_content = self.fetch_rss_feed(rss_url)
        if not rss_content:
            return

        # RSS 파싱
        rss_items = self.parse_rss_feed(rss_content)
        if not rss_items:
            self.logger.warning(f"RSS 아이템이 없습니다: {committee}")
            return

        # 지정된 개수만큼만 처리
        items_to_process = rss_items[:max_items]

        for i, item in enumerate(items_to_process, 1):
            try:
                self.logger.info(f"{committee} 기사 처리 중: {i}/{len(items_to_process)} - {item['title'][:50]}...")

                # 기사 상세 내용 추출
                if item["link"]:
                    article_detail = self.extract_article_content(item["link"])

                    article_data = {
                        "committee": committee,
                        "committee_category": self.get_committee_category(committee),
                        "business_area": self.committee_areas.get(committee, ""),
                        "title": item["title"],
                        "link": item["link"],
                        "pub_date": item["pub_date"],
                        "creator": item["creator"],
                        "description": item["description"],
                        "content": article_detail["content"],
                        "contact_info": article_detail["contact_info"],
                        "regulation_keywords": article_detail["regulation_keywords"],
                        "decision_type": article_detail["decision_type"],
                        "relevant_keywords": self.get_relevant_keywords(committee, article_detail["content"]),
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    self.articles.append(article_data)

                # 딜레이
                self.random_delay(1, 3)

            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue

        self.logger.info(f"{committee} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_committees(self, max_items_per_committee=30):
        """모든 위원회 RSS 피드 크롤링"""
        total_committees = len(self.committee_feeds)
        self.logger.info(f"전체 {total_committees}개 위원회 RSS 피드 크롤링 시작")

        for i, (committee, rss_url) in enumerate(self.committee_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_committees}] {committee} 피드 크롤링 중...")
                self.crawl_committee_feed(committee, rss_url, max_items_per_committee)

                # 위원회 간 딜레이
                if i < total_committees:
                    self.random_delay(3, 6)

            except Exception as e:
                self.logger.error(f"{committee} 위원회 크롤링 오류: {e}")
                continue

        self.logger.info(f"전체 위원회 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_committees(self, committee_names, max_items_per_committee=30):
        """특정 위원회들만 크롤링"""
        for committee_name in committee_names:
            if committee_name in self.committee_feeds:
                self.crawl_committee_feed(committee_name, self.committee_feeds[committee_name], max_items_per_committee)
            else:
                self.logger.warning(f"존재하지 않는 위원회: {committee_name}")
                available_committees = list(self.committee_feeds.keys())
                self.logger.info(f"사용 가능한 위원회: {available_committees}")

    def crawl_by_category(self, categories, max_items_per_committee=25):
        """카테고리별 위원회 크롤링"""
        target_committees = []

        for category in categories:
            if category in self.committee_categories:
                target_committees.extend(self.committee_categories[category])
            else:
                self.logger.warning(f"존재하지 않는 카테고리: {category}")

        if target_committees:
            self.logger.info(f"카테고리 '{', '.join(categories)}'에 해당하는 위원회: {target_committees}")
            self.crawl_specific_committees(target_committees, max_items_per_committee)
        else:
            self.logger.warning(f"해당 카테고리에 맞는 위원회를 찾을 수 없습니다: {categories}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/위원회별_RSS_{timestamp}.csv"

        # 고정 컬럼 순서로 CSV 저장
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for art in self.articles:
                    writer.writerow(
                        {
                            "언론사": "정책포털_위원회별",
                            "제목": art.get("title", ""),
                            "날짜": art.get("pub_date", ""),
                            "카테고리": art.get("committee_category", ""),
                            "기자명": "정책포털",
                            "본문": art.get("description", ""),
                        }
                    )
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_committee(self):
        """위원회별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for committee in df["committee"].unique():
            committee_df = df[df["committee"] == committee]
            filename = f"results/위원회_{committee}_{timestamp}.csv"
            committee_df.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"{committee} 저장 완료: {filename} ({len(committee_df)}개 기사)")

    def save_by_category(self):
        """카테고리별로 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for category in df["committee_category"].unique():
            category_df = df[df["committee_category"] == category]
            filename = f"results/위원회카테고리_{category}_{timestamp}.csv"
            category_df.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"{category} 카테고리 저장 완료: {filename} ({len(category_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return

        df = pd.DataFrame(self.articles)

        print("\n" + "=" * 60)
        print("정부 위원회별 RSS 크롤링 통계")
        print("=" * 60)

        # 위원회별 통계
        committee_stats = df["committee"].value_counts()
        print(f"\n🏛️ 위원회별 기사 수:")
        for committee, count in committee_stats.items():
            business_area = self.committee_areas.get(committee, "")
            print(f"  • {committee} ({business_area}): {count}개")

        # 카테고리별 통계
        category_stats = df["committee_category"].value_counts()
        print(f"\n📊 카테고리별 기사 수:")
        for category, count in category_stats.items():
            print(f"  • {category}: {count}개")

        # 의결/결정 유형별 통계
        decision_stats = df[df["decision_type"] != ""]["decision_type"].value_counts().head(8)
        if not decision_stats.empty:
            print(f"\n⚖️ 주요 의결/결정 유형별 기사 수:")
            for decision_type, count in decision_stats.items():
                print(f"  • {decision_type}: {count}개")

        # 규제 키워드 통계
        regulation_available = len(df[df["regulation_keywords"] != ""])
        print(f"\n📋 규제/정책 키워드:")
        print(f"  • 키워드 추출 성공: {regulation_available}개")
        print(f"  • 키워드 추출 실패: {len(df) - regulation_available}개")

        # 연락처 정보 통계
        contact_available = len(df[df["contact_info"] != ""])
        print(f"\n📞 연락처 정보:")
        print(f"  • 연락처 추출 성공: {contact_available}개")
        print(f"  • 연락처 추출 실패: {len(df) - contact_available}개")

        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 위원회 수: {len(committee_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 관련 키워드 매칭: {len(df[df['relevant_keywords'] != ''])}개")
        print("=" * 60)

    def get_available_committees(self):
        """사용 가능한 위원회 목록 반환"""
        return list(self.committee_feeds.keys())

    def get_categories(self):
        """카테고리 목록 반환"""
        return list(self.committee_categories.keys())


def main():
    """메인 실행 함수"""
    print("정책브리핑 정부 위원회별 RSS 크롤러")
    print("=" * 50)

    crawler = KoreaCommitteeRSSCrawler()

    # 자동 전체 위원회 크롤링 (각 위원회당 20개씩)
    print("전체 위원회 RSS 피드 크롤링을 시작합니다... (각 위원회당 20건)")
    crawler.crawl_all_committees(max_items_per_committee=20)

    # CSV 저장
    crawler.save_to_csv()

    print("\n위원회별 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
