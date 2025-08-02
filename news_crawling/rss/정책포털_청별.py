#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
정책브리핑(korea.kr) 정부 산하기관별 RSS 크롤링 코드
18개 정부 산하기관 RSS 피드 전용 크롤러

작성일: 2025-08-02
"""

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

class KoreaGovernmentAgencyRSSCrawler:
    def __init__(self):
        """정책브리핑 정부 산하기관별 RSS 크롤러 초기화"""
        self.base_url = "https://www.korea.kr"
        
        # 18개 정부 산하기관 RSS 피드
        self.agency_feeds = {
            '국세청': 'https://www.korea.kr/rss/dept_nts.xml',
            '관세청': 'https://www.korea.kr/rss/dept_customs.xml',
            '조달청': 'https://www.korea.kr/rss/dept_pps.xml',
            '통계청': 'https://www.korea.kr/rss/dept_kostat.xml',
            '우주항공청': 'https://www.korea.kr/rss/dept_kasa.xml',
            '재외동포청': 'https://www.korea.kr/rss/dept_oka.xml',
            '검찰청': 'https://www.korea.kr/rss/dept_spo.xml',
            '병무청': 'https://www.korea.kr/rss/dept_mma.xml',
            '방위사업청': 'https://www.korea.kr/rss/dept_dapa.xml',
            '경찰청': 'https://www.korea.kr/rss/dept_npa.xml',
            '소방청': 'https://www.korea.kr/rss/dept_nfa.xml',
            '국가유산청': 'https://www.korea.kr/rss/dept_khs.xml',
            '농촌진흥청': 'https://www.korea.kr/rss/dept_rda.xml',
            '산림청': 'https://www.korea.kr/rss/dept_forest.xml',
            '특허청': 'https://www.korea.kr/rss/dept_kipo.xml',
            '질병관리청': 'https://www.korea.kr/rss/dept_kdca.xml',
            '기상청': 'https://www.korea.kr/rss/dept_kma.xml',
            '행정중심복합도시건설청': 'https://www.korea.kr/rss/dept_macc.xml',
            '새만금개발청': 'https://www.korea.kr/rss/dept_sda.xml',
            '해양경찰청': 'https://www.korea.kr/rss/dept_kcg.xml'
        }
        
        # 산하기관별 주요 업무 분야 (분석용)
        self.agency_areas = {
            '국세청': '세무행정, 국세징수, 세무조사',
            '관세청': '관세행정, 수출입통관, 밀수단속',
            '조달청': '공공조달, 정부구매, 물품관리',
            '통계청': '국가통계, 인구조사, 경제통계',
            '우주항공청': '우주개발, 항공우주기술, 위성',
            '재외동포청': '재외동포지원, 해외한인사회',
            '검찰청': '검찰업무, 형사사법, 수사',
            '병무청': '병역행정, 징병검사, 군복무',
            '방위사업청': '방산업무, 무기체계, 국방획득',
            '경찰청': '치안행정, 범죄수사, 교통안전',
            '소방청': '화재예방, 구급구조, 재난대응',
            '국가유산청': '문화재보호, 역사유적, 전통문화',
            '농촌진흥청': '농업기술, 농촌개발, 농업연구',
            '산림청': '산림보호, 임업정책, 산불방지',
            '특허청': '특허행정, 지식재산권, 상표등록',
            '질병관리청': '질병예방, 감염병관리, 방역',
            '기상청': '기상예보, 날씨정보, 기후변화',
            '행정중심복합도시건설청': '세종시건설, 도시개발',
            '새만금개발청': '새만금개발, 간척사업',
            '해양경찰청': '해상치안, 해양안전, 해상구조'
        }
        
        # 산하기관 카테고리 분류
        self.agency_categories = {
            '세무·재정': ['국세청', '관세청', '조달청'],
            '통계·정보': ['통계청'],
            '과학·우주': ['우주항공청'],
            '외교·동포': ['재외동포청'],
            '사법·치안': ['검찰청', '경찰청', '해양경찰청'],
            '국방·병무': ['병무청', '방위사업청'],
            '안전·방재': ['소방청', '질병관리청'],
            '문화·유산': ['국가유산청'],
            '농림·수산': ['농촌진흥청', '산림청'],
            '산업·특허': ['특허청'],
            '기상·환경': ['기상청'],
            '도시·개발': ['행정중심복합도시건설청', '새만금개발청']
        }
        
        # User-Agent 리스트
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        
        self.articles = []
        self.session = requests.Session()
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 헤더 생성"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
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
                response.encoding = 'utf-8'
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
            
            for item in root.findall('.//item'):
                article_info = {}
                
                # 기본 정보 추출
                title_elem = item.find('title')
                article_info['title'] = title_elem.text.strip() if title_elem is not None else ''
                
                link_elem = item.find('link')
                article_info['link'] = link_elem.text.strip() if link_elem is not None else ''
                
                pubdate_elem = item.find('pubDate')
                article_info['pub_date'] = pubdate_elem.text.strip() if pubdate_elem is not None else ''
                
                guid_elem = item.find('guid')
                article_info['guid'] = guid_elem.text.strip() if guid_elem is not None else ''
                
                # dc:creator 추출 (네임스페이스 고려)
                creator_elem = item.find('.//{http://purl.org/dc/elements/1.1/}creator')
                article_info['creator'] = creator_elem.text.strip() if creator_elem is not None else ''
                
                # description에서 간단한 내용 추출
                desc_elem = item.find('description')
                if desc_elem is not None:
                    desc_text = desc_elem.text or ''
                    # CDATA 처리
                    if desc_text.startswith('<![CDATA[') and desc_text.endswith(']]>'):
                        desc_text = desc_text[9:-3]
                    
                    # HTML 태그 제거하여 텍스트만 추출
                    soup = BeautifulSoup(desc_text, 'html.parser')
                    article_info['description'] = soup.get_text().strip()[:300] + '...' if len(soup.get_text().strip()) > 300 else soup.get_text().strip()
                else:
                    article_info['description'] = ''
                
                items.append(article_info)
            
            return items
        except Exception as e:
            self.logger.error(f"RSS 파싱 오류: {e}")
            return []

    def extract_article_content(self, article_url, max_retries=3):
        """개별 기사 본문 추출 - 산하기관 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 산하기관별 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    '.agency_cont',     # 산하기관 콘텐츠
                    '.press_cont',      # 보도자료 콘텐츠
                    '.article_body',    # 일반 기사
                    '.rbody',          # 브리핑 페이지
                    '.view_cont',      # 뷰 페이지
                    '.cont_body',      # 콘텐츠 본문
                    '.policy_body',    # 정책 본문
                    '.briefing_cont',  # 브리핑 내용
                    '.news_cont',      # 뉴스 내용
                    '.notice_cont',    # 공지사항 내용
                    '.info_cont'       # 정보 내용
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
                    for elem in soup.find_all(['header', 'footer', 'nav', 'aside', 'script', 'style']):
                        elem.decompose()
                    
                    main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('body')
                    if main_content:
                        content = main_content.get_text().strip()
                
                # 기관별 특화 정보 추출
                contact_info = self.extract_agency_contact_info(content)
                service_keywords = self.extract_service_keywords(content)
                
                # 텍스트 정리
                content = re.sub(r'\s+', ' ', content).strip()
                
                return {
                    'content': content[:3000] + '...' if len(content) > 3000 else content,
                    'contact_info': contact_info,
                    'service_keywords': service_keywords
                }
                
            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {'content': '추출 실패', 'contact_info': '', 'service_keywords': ''}

    def extract_agency_contact_info(self, content):
        """산하기관 연락처/담당자 정보 추출"""
        # 산하기관별 연락처 정보 추출 패턴
        patterns = [
            r'문의\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'담당\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'연락처\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'문의처\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'담당부서\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'담당자\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'홈페이지\s*:\s*(https?://[^\s]+)',
            r'([가-힣]+청|[가-힣]+청|[가-힣]+원|[가-힣]+소)\s+([가-힣]+과|[가-힣]+팀|[가-힣]+국)\s*(?:\(([^)]+)\))?'
        ]
        
        contact_info = {}
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) >= 2:
                        dept = match[0].strip() if match[0] else ''
                        contact = match[1].strip() if match[1] else ''
                        
                        if dept and len(dept) > 1 and len(dept) < 100:
                            contact_info['department'] = dept
                        if contact and ('02-' in contact or '044-' in contact or '070-' in contact or 'http' in contact):
                            if 'http' in contact:
                                contact_info['website'] = contact
                            else:
                                contact_info['phone'] = contact
                else:
                    if match and len(match) > 1 and len(match) < 100:
                        contact_info['department'] = match.strip()
        
        return '; '.join([f"{k}: {v}" for k, v in contact_info.items()])

    def extract_service_keywords(self, content):
        """산하기관 서비스/업무 키워드 추출"""
        # 산하기관별 주요 서비스 키워드 패턴
        service_patterns = [
            r'(신청|접수|발급|등록|승인|허가|인증|검사|검증)',
            r'(서비스|지원|상담|안내|정보제공|교육|훈련)',
            r'(온라인|전자|디지털|모바일|앱|시스템)',
            r'(수수료|요금|비용|기준|절차|방법)',
            r'(안전|보안|예방|점검|관리|감시|단속)',
            r'(개선|개발|연구|조사|분석|평가)',
            r'(국민|시민|업체|기업|사업자|개인)'
        ]
        
        keywords = set()
        for pattern in service_patterns:
            matches = re.findall(pattern, content)
            keywords.update(matches)
        
        return ', '.join(list(keywords)[:10])  # 최대 10개 키워드

    def get_agency_category(self, agency_name):
        """산하기관의 카테고리 반환"""
        for category, agencies in self.agency_categories.items():
            if agency_name in agencies:
                return category
        return '기타'

    def crawl_agency_feed(self, agency, rss_url, max_items=25):
        """개별 산하기관 RSS 피드 크롤링"""
        self.logger.info(f"산하기관 크롤링 시작: {agency}")
        
        # RSS 피드 가져오기
        rss_content = self.fetch_rss_feed(rss_url)
        if not rss_content:
            return
        
        # RSS 파싱
        rss_items = self.parse_rss_feed(rss_content)
        if not rss_items:
            self.logger.warning(f"RSS 아이템이 없습니다: {agency}")
            return
        
        # 지정된 개수만큼만 처리
        items_to_process = rss_items[:max_items]
        
        for i, item in enumerate(items_to_process, 1):
            try:
                self.logger.info(f"{agency} 기사 처리 중: {i}/{len(items_to_process)} - {item['title'][:50]}...")
                
                # 기사 상세 내용 추출
                if item['link']:
                    article_detail = self.extract_article_content(item['link'])
                    
                    article_data = {
                        'agency': agency,
                        'agency_category': self.get_agency_category(agency),
                        'business_area': self.agency_areas.get(agency, ''),
                        'title': item['title'],
                        'link': item['link'],
                        'pub_date': item['pub_date'],
                        'creator': item['creator'],
                        'description': item['description'],
                        'content': article_detail['content'],
                        'contact_info': article_detail['contact_info'],
                        'service_keywords': article_detail['service_keywords'],
                        'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    self.articles.append(article_data)
                
                # 딜레이
                self.random_delay(1, 3)
                
            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue
        
        self.logger.info(f"{agency} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_agencies(self, max_items_per_agency=25):
        """모든 산하기관 RSS 피드 크롤링"""
        total_agencies = len(self.agency_feeds)
        self.logger.info(f"전체 {total_agencies}개 산하기관 RSS 피드 크롤링 시작")
        
        for i, (agency, rss_url) in enumerate(self.agency_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_agencies}] {agency} 피드 크롤링 중...")
                self.crawl_agency_feed(agency, rss_url, max_items_per_agency)
                
                # 기관 간 딜레이
                if i < total_agencies:
                    self.random_delay(3, 6)
                    
            except Exception as e:
                self.logger.error(f"{agency} 산하기관 크롤링 오류: {e}")
                continue
        
        self.logger.info(f"전체 산하기관 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_agencies(self, agency_names, max_items_per_agency=25):
        """특정 산하기관들만 크롤링"""
        for agency_name in agency_names:
            if agency_name in self.agency_feeds:
                self.crawl_agency_feed(agency_name, self.agency_feeds[agency_name], max_items_per_agency)
            else:
                self.logger.warning(f"존재하지 않는 산하기관: {agency_name}")
                available_agencies = list(self.agency_feeds.keys())
                self.logger.info(f"사용 가능한 산하기관: {available_agencies}")

    def crawl_by_category(self, categories, max_items_per_agency=20):
        """카테고리별 산하기관 크롤링"""
        target_agencies = []
        
        for category in categories:
            if category in self.agency_categories:
                target_agencies.extend(self.agency_categories[category])
            else:
                self.logger.warning(f"존재하지 않는 카테고리: {category}")
        
        if target_agencies:
            self.logger.info(f"카테고리 '{', '.join(categories)}'에 해당하는 산하기관: {target_agencies}")
            self.crawl_specific_agencies(target_agencies, max_items_per_agency)
        else:
            self.logger.warning(f"해당 카테고리에 맞는 산하기관을 찾을 수 없습니다: {categories}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'results/산하기관별_RSS_{timestamp}.csv'
        
        try:
            df = pd.DataFrame(self.articles)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_agency(self):
        """산하기관별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for agency in df['agency'].unique():
            agency_df = df[df['agency'] == agency]
            filename = f'results/산하기관_{agency}_{timestamp}.csv'
            agency_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{agency} 저장 완료: {filename} ({len(agency_df)}개 기사)")

    def save_by_category(self):
        """카테고리별로 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for category in df['agency_category'].unique():
            category_df = df[df['agency_category'] == category]
            filename = f'results/카테고리_{category}_{timestamp}.csv'
            category_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{category} 카테고리 저장 완료: {filename} ({len(category_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return
        
        df = pd.DataFrame(self.articles)
        
        print("\n" + "="*60)
        print("정부 산하기관별 RSS 크롤링 통계")
        print("="*60)
        
        # 산하기관별 통계
        agency_stats = df['agency'].value_counts()
        print(f"\n🏢 산하기관별 기사 수:")
        for agency, count in agency_stats.items():
            business_area = self.agency_areas.get(agency, '')
            print(f"  • {agency} ({business_area}): {count}개")
        
        # 카테고리별 통계
        category_stats = df['agency_category'].value_counts()
        print(f"\n📊 카테고리별 기사 수:")
        for category, count in category_stats.items():
            print(f"  • {category}: {count}개")
        
        # 업무 분야별 통계
        business_area_stats = df['business_area'].value_counts().head(10)
        if not business_area_stats.empty:
            print(f"\n💼 주요 업무 분야별 기사 수:")
            for area, count in business_area_stats.items():
                print(f"  • {area}: {count}개")
        
        # 연락처 정보 통계
        contact_available = len(df[df['contact_info'] != ''])
        print(f"\n📞 연락처 정보:")
        print(f"  • 연락처 추출 성공: {contact_available}개")
        print(f"  • 연락처 추출 실패: {len(df) - contact_available}개")
        
        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 산하기관 수: {len(agency_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 서비스 키워드 추출: {len(df[df['service_keywords'] != ''])}개")
        print("="*60)

    def get_available_agencies(self):
        """사용 가능한 산하기관 목록 반환"""
        return list(self.agency_feeds.keys())

    def get_categories(self):
        """카테고리 목록 반환"""
        return list(self.agency_categories.keys())


def main():
    """메인 실행 함수"""
    print("정책브리핑 정부 산하기관별 RSS 크롤러")
    print("="*50)
    
    crawler = KoreaGovernmentAgencyRSSCrawler()
    
    # 사용 예시 1: 전체 산하기관 크롤링 (각 기관당 15개씩)
    print("전체 산하기관 RSS 피드 크롤링을 시작합니다...")
    crawler.crawl_all_agencies(max_items_per_agency=10)
    
    # CSV 저장
    crawler.save_to_csv()
    
    # 산하기관별 개별 파일 저장
    # crawler.save_by_agency()
    
    # 카테고리별 파일 저장
    # crawler.save_by_category()
    
    # 사용 예시 2: 특정 산하기관만 크롤링
    # crawler.crawl_specific_agencies(['국세청', '관세청', '통계청'])
    
    # 사용 예시 3: 카테고리별 크롤링
    # crawler.crawl_by_category(['세무·재정', '사법·치안'], max_items_per_agency=20)
    
    print("\n산하기관별 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
