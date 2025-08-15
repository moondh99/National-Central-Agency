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


class KoreaDepartmentRSSCrawler:
    def __init__(self):
        """정책브리핑 부처별 RSS 크롤러 초기화"""
        self.base_url = "https://www.korea.kr"

        # 22개 부처별 RSS 피드
        self.department_feeds = {
            "국무조정실": "https://www.korea.kr/rss/dept_opm.xml",
            "기획재정부": "https://www.korea.kr/rss/dept_moef.xml",
            "교육부": "https://www.korea.kr/rss/dept_moe.xml",
            "과학기술정보통신부": "https://www.korea.kr/rss/dept_msit.xml",
            "외교부": "https://www.korea.kr/rss/dept_mofa.xml",
            "통일부": "https://www.korea.kr/rss/dept_unikorea.xml",
            "법무부": "https://www.korea.kr/rss/dept_moj.xml",
            "국방부": "https://www.korea.kr/rss/dept_mnd.xml",
            "행정안전부": "https://www.korea.kr/rss/dept_mois.xml",
            "국가보훈부": "https://www.korea.kr/rss/dept_mpva.xml",
            "문화체육관광부": "https://www.korea.kr/rss/dept_mcst.xml",
            "농림축산식품부": "https://www.korea.kr/rss/dept_mafra.xml",
            "산업통상자원부": "https://www.korea.kr/rss/dept_motie.xml",
            "보건복지부": "https://www.korea.kr/rss/dept_mw.xml",
            "환경부": "https://www.korea.kr/rss/dept_me.xml",
            "고용노동부": "https://www.korea.kr/rss/dept_moel.xml",
            "여성가족부": "https://www.korea.kr/rss/dept_mogef.xml",
            "국토교통부": "https://www.korea.kr/rss/dept_molit.xml",
            "해양수산부": "https://www.korea.kr/rss/dept_mof.xml",
            "중소벤처기업부": "https://www.korea.kr/rss/dept_mss.xml",
            "인사혁신처": "https://www.korea.kr/rss/dept_mpm.xml",
            "법제처": "https://www.korea.kr/rss/dept_moleg.xml",
            "식품의약품안전처": "https://www.korea.kr/rss/dept_mfds.xml",
        }

        # 부처별 주요 정책 분야 (분석용)
        self.department_areas = {
            "국무조정실": "정부 정책 조정",
            "기획재정부": "경제정책, 예산, 세제",
            "교육부": "교육정책, 대학, 평생교육",
            "과학기술정보통신부": "ICT, 과학기술, 방송통신",
            "외교부": "외교, 국제관계, 해외동포",
            "통일부": "통일정책, 북한, 남북관계",
            "법무부": "법무행정, 출입국, 인권",
            "국방부": "국방정책, 병무, 국방산업",
            "행정안전부": "행정혁신, 지방자치, 안전관리",
            "국가보훈부": "국가유공자, 보훈복지",
            "문화체육관광부": "문화예술, 체육, 관광, 종교",
            "농림축산식품부": "농업, 축산, 식품안전",
            "산업통상자원부": "산업정책, 에너지, 통상",
            "보건복지부": "보건의료, 복지, 인구정책",
            "환경부": "환경보전, 기후변화, 상하수도",
            "고용노동부": "고용정책, 노동, 산업안전",
            "여성가족부": "여성정책, 가족, 청소년",
            "국토교통부": "국토개발, 교통, 주택, 건설",
            "해양수산부": "해양정책, 수산업, 해운항만",
            "중소벤처기업부": "중소기업, 벤처, 소상공인",
            "인사혁신처": "공무원 인사, 조직관리",
            "법제처": "법령정비, 법제업무",
            "식품의약품안전처": "식품안전, 의약품, 화장품",
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
        """개별 기사 본문 추출 - 부처 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"

                soup = BeautifulSoup(response.text, "html.parser")

                # 부처별 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    ".dept_cont",  # 부처 콘텐츠
                    ".press_cont",  # 보도자료 콘텐츠
                    ".article_body",  # 일반 기사
                    ".rbody",  # 브리핑 페이지
                    ".view_cont",  # 뷰 페이지
                    ".cont_body",  # 콘텐츠 본문
                    ".policy_body",  # 정책 본문
                    ".briefing_cont",  # 브리핑 내용
                    ".news_cont",  # 뉴스 내용
                    ".ministry_cont",  # 부처 공지사항
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

                # 부처명/담당자/연락처 정보 추출
                contact_info = self.extract_contact_info(content)
                policy_keywords = self.extract_policy_keywords(content)

                # 텍스트 정리
                content = re.sub(r"\s+", " ", content).strip()

                return {
                    "content": content[:3000] + "..." if len(content) > 3000 else content,
                    "contact_info": contact_info,
                    "policy_keywords": policy_keywords,
                }

            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {"content": "추출 실패", "contact_info": "", "policy_keywords": ""}

    def extract_contact_info(self, content):
        """연락처/담당자 정보 추출 - 부처별 특화"""
        # 부처별 연락처 정보 추출 패턴
        patterns = [
            r"문의\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"연락처\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"문의처\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당부서\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"담당자\s*:\s*([^(]+?)(?:\(([^)]+)\))?",
            r"([가-힣]+부|[가-힣]+청|[가-힣]+원|[가-힣]+실|[가-힣]+위원회|[가-힣]+처)\s+([가-힣]+과|[가-힣]+팀|[가-힣]+국)\s*(?:\(([^)]+)\))?",
        ]

        contact_info = {}

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    dept = match[0].strip() if match[0] else ""
                    phone = match[1].strip() if len(match) > 1 and match[1] else ""

                    if dept and len(dept) > 1 and len(dept) < 100:
                        contact_info["department"] = dept
                    if phone and ("02-" in phone or "044-" in phone or "070-" in phone):
                        contact_info["phone"] = phone
                else:
                    dept = match.strip()
                    if dept and len(dept) > 1 and len(dept) < 100:
                        contact_info["department"] = dept

        return "; ".join([f"{k}: {v}" for k, v in contact_info.items()])

    def extract_policy_keywords(self, content):
        """정책 키워드 추출"""
        # 주요 정책 키워드 패턴
        policy_patterns = [
            r"(정책|제도|방안|계획|사업|프로그램|지원|개선|강화|확대|도입|시행|추진)",
            r"(예산|투자|지원금|보조금|융자|세제|혜택)",
            r"(법령|규정|기준|가이드라인|매뉴얼)",
            r"(개혁|혁신|디지털|스마트|그린|친환경)",
            r"(안전|보안|예방|대응|관리)",
            r"(일자리|고용|창업|산업|경제)",
            r"(복지|건강|교육|문화|환경)",
        ]

        keywords = set()
        for pattern in policy_patterns:
            matches = re.findall(pattern, content)
            keywords.update(matches)

        return ", ".join(list(keywords)[:10])  # 최대 10개 키워드

    def crawl_department_feed(self, department, rss_url, max_items=30):
        """개별 부처 RSS 피드 크롤링"""
        self.logger.info(f"부처 크롤링 시작: {department}")

        # RSS 피드 가져오기
        rss_content = self.fetch_rss_feed(rss_url)
        if not rss_content:
            return

        # RSS 파싱
        rss_items = self.parse_rss_feed(rss_content)
        if not rss_items:
            self.logger.warning(f"RSS 아이템이 없습니다: {department}")
            return

        # 지정된 개수만큼만 처리
        items_to_process = rss_items[:max_items]

        for i, item in enumerate(items_to_process, 1):
            try:
                self.logger.info(f"{department} 기사 처리 중: {i}/{len(items_to_process)} - {item['title'][:50]}...")

                # 기사 상세 내용 추출
                if item["link"]:
                    article_detail = self.extract_article_content(item["link"])

                    article_data = {
                        "department": department,
                        "policy_area": self.department_areas.get(department, ""),
                        "title": item["title"],
                        "link": item["link"],
                        "pub_date": item["pub_date"],
                        "creator": item["creator"],
                        "description": item["description"],
                        "content": article_detail["content"],
                        "contact_info": article_detail["contact_info"],
                        "policy_keywords": article_detail["policy_keywords"],
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    self.articles.append(article_data)

                # 딜레이
                self.random_delay(1, 3)

            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue

        self.logger.info(f"{department} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_departments(self, max_items_per_department=30):
        """모든 부처 RSS 피드 크롤링"""
        total_departments = len(self.department_feeds)
        self.logger.info(f"전체 {total_departments}개 부처 RSS 피드 크롤링 시작")

        for i, (department, rss_url) in enumerate(self.department_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_departments}] {department} 피드 크롤링 중...")
                self.crawl_department_feed(department, rss_url, max_items_per_department)

                # 부처 간 딜레이
                if i < total_departments:
                    self.random_delay(3, 6)

            except Exception as e:
                self.logger.error(f"{department} 부처 크롤링 오류: {e}")
                continue

        self.logger.info(f"전체 부처 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_departments(self, department_names, max_items_per_department=30):
        """특정 부처들만 크롤링"""
        for dept_name in department_names:
            if dept_name in self.department_feeds:
                self.crawl_department_feed(dept_name, self.department_feeds[dept_name], max_items_per_department)
            else:
                self.logger.warning(f"존재하지 않는 부처: {dept_name}")
                available_depts = list(self.department_feeds.keys())
                self.logger.info(f"사용 가능한 부처: {available_depts}")

    def crawl_by_policy_area(self, policy_areas, max_items_per_department=20):
        """정책 분야별 부처 크롤링"""
        target_departments = []

        for dept, area in self.department_areas.items():
            for policy_area in policy_areas:
                if policy_area in area:
                    target_departments.append(dept)
                    break

        if target_departments:
            self.logger.info(f"정책 분야 '{', '.join(policy_areas)}'에 해당하는 부처: {target_departments}")
            self.crawl_specific_departments(target_departments, max_items_per_department)
        else:
            self.logger.warning(f"해당 정책 분야에 맞는 부처를 찾을 수 없습니다: {policy_areas}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/부처별_RSS_{timestamp}.csv"

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
                            "언론사": "정책포털_부처별",
                            "제목": art.get("title", ""),
                            "날짜": art.get("pub_date", ""),
                            "카테고리": art.get("policy_area", ""),
                            "기자명": "정책포털",
                            "본문": art.get("description", ""),
                        }
                    )
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_department(self):
        """부처별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return

        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for department in df["department"].unique():
            dept_df = df[df["department"] == department]
            filename = f"results/부처별_{department}_{timestamp}.csv"
            dept_df.to_csv(filename, index=False, encoding="utf-8-sig")
            self.logger.info(f"{department} 저장 완료: {filename} ({len(dept_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return

        df = pd.DataFrame(self.articles)

        print("\n" + "=" * 60)
        print("부처별 RSS 크롤링 통계")
        print("=" * 60)

        # 부처별 통계
        dept_stats = df["department"].value_counts()
        print(f"\n🏛️ 부처별 기사 수:")
        for dept, count in dept_stats.items():
            policy_area = self.department_areas.get(dept, "")
            print(f"  • {dept} ({policy_area}): {count}개")

        # 정책 분야별 통계
        policy_area_stats = df["policy_area"].value_counts().head(10)
        if not policy_area_stats.empty:
            print(f"\n📊 주요 정책 분야별 기사 수:")
            for area, count in policy_area_stats.items():
                print(f"  • {area}: {count}개")

        # 연락처 정보 통계
        contact_available = len(df[df["contact_info"] != ""])
        print(f"\n📞 연락처 정보:")
        print(f"  • 연락처 추출 성공: {contact_available}개")
        print(f"  • 연락처 추출 실패: {len(df) - contact_available}개")

        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 부처 수: {len(dept_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 정책 키워드 추출: {len(df[df['policy_keywords'] != ''])}개")
        print("=" * 60)

    def get_available_departments(self):
        """사용 가능한 부처 목록 반환"""
        return list(self.department_feeds.keys())

    def get_policy_areas(self):
        """정책 분야 목록 반환"""
        return list(set(self.department_areas.values()))


def main():
    """메인 실행 함수"""
    print("정책브리핑 부처별 RSS 크롤러")
    print("=" * 50)

    crawler = KoreaDepartmentRSSCrawler()

    # 사용 예시 1: 전체 부처 크롤링 (각 부처당 20개씩)
    print("전체 부처 RSS 피드 크롤링을 시작합니다... (각 부처당 20건)")
    crawler.crawl_all_departments(max_items_per_department=20)

    # CSV 저장
    crawler.save_to_csv()

    print("\n부처별 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
