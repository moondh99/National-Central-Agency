#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
정책브리핑(korea.kr) 대통령직속위원회별 RSS 크롤링 코드
4개 대통령직속위원회 RSS 피드 전용 크롤러

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

class PresidentialCommitteeRSSCrawler:
    def __init__(self):
        """정책브리핑 대통령직속위원회별 RSS 크롤러 초기화"""
        self.base_url = "https://www.korea.kr"
        
        # 4개 대통령직속위원회 RSS 피드
        self.presidential_committee_feeds = {
            '국민통합위원회': 'https://www.korea.kr/rss/dept_k_cohesion.xml',
            '저출산고령사회위원회': 'https://www.korea.kr/rss/dept_betterfuture.xml',
            '경제사회노동위원회': 'https://www.korea.kr/rss/dept_esdc.xml',
            '탄소중립녹색성장위원회': 'https://www.korea.kr/rss/dept_cnc.xml'
        }
        
        # 대통령직속위원회별 주요 업무 분야 (분석용)
        self.committee_areas = {
            '국민통합위원회': '사회통합, 갈등해결, 국민화합, 소통정책',
            '저출산고령사회위원회': '저출산정책, 고령사회대응, 인구정책, 가족정책',
            '경제사회노동위원회': '노사관계, 경제민주화, 사회대화, 노동정책',
            '탄소중립녹색성장위원회': '탄소중립, 그린뉴딜, 기후변화대응, 친환경정책'
        }
        
        # 위원회 카테고리 분류
        self.committee_categories = {
            '사회·통합': ['국민통합위원회'],
            '인구·복지': ['저출산고령사회위원회'],
            '노동·경제': ['경제사회노동위원회'],
            '환경·기후': ['탄소중립녹색성장위원회']
        }
        
        # 위원회별 주요 키워드
        self.committee_keywords = {
            '국민통합위원회': ['통합', '화합', '갈등', '소통', '협치', '상생', '대화', '포용'],
            '저출산고령사회위원회': ['저출산', '고령화', '인구', '출산', '육아', '보육', '노인', '실버'],
            '경제사회노동위원회': ['노사', '노동', '임금', '일자리', '고용', '근로', '사회대화', '협약'],
            '탄소중립녹색성장위원회': ['탄소중립', '그린뉴딜', '친환경', '재생에너지', '기후변화', '온실가스', '넷제로']
        }
        
        # 위원회별 주요 정책 방향
        self.policy_directions = {
            '국민통합위원회': '사회 갈등 해소 및 국민 화합 도모',
            '저출산고령사회위원회': '저출산·고령사회 대응 정책 수립',
            '경제사회노동위원회': '노사 간 대화와 협력을 통한 상생발전',
            '탄소중립녹색성장위원회': '2050 탄소중립 달성 및 녹색성장 추진'
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
                    article_info['description'] = soup.get_text().strip()[:400] + '...' if len(soup.get_text().strip()) > 400 else soup.get_text().strip()
                else:
                    article_info['description'] = ''
                
                items.append(article_info)
            
            return items
        except Exception as e:
            self.logger.error(f"RSS 파싱 오류: {e}")
            return []

    def extract_article_content(self, article_url, max_retries=3):
        """개별 기사 본문 추출 - 대통령직속위원회 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 대통령직속위원회별 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    '.presidential_cont',  # 대통령직속 콘텐츠
                    '.committee_cont',     # 위원회 콘텐츠
                    '.policy_cont',        # 정책 콘텐츠
                    '.press_cont',         # 보도자료 콘텐츠
                    '.meeting_cont',       # 회의 콘텐츠
                    '.article_body',       # 일반 기사
                    '.rbody',             # 브리핑 페이지
                    '.view_cont',         # 뷰 페이지
                    '.cont_body',         # 콘텐츠 본문
                    '.policy_body',       # 정책 본문
                    '.briefing_cont',     # 브리핑 내용
                    '.news_cont',         # 뉴스 내용
                    '.agenda_cont'        # 의제 내용
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
                
                # 대통령직속위원회별 특화 정보 추출
                contact_info = self.extract_presidential_contact_info(content)
                policy_keywords = self.extract_policy_keywords(content)
                meeting_type = self.extract_meeting_type(content)
                stakeholders = self.extract_stakeholders(content)
                
                # 텍스트 정리
                content = re.sub(r'\s+', ' ', content).strip()
                
                return {
                    'content': content[:4000] + '...' if len(content) > 4000 else content,
                    'contact_info': contact_info,
                    'policy_keywords': policy_keywords,
                    'meeting_type': meeting_type,
                    'stakeholders': stakeholders
                }
                
            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {'content': '추출 실패', 'contact_info': '', 'policy_keywords': '', 'meeting_type': '', 'stakeholders': ''}

    def extract_presidential_contact_info(self, content):
        """대통령직속위원회 연락처/담당자 정보 추출"""
        # 대통령직속위원회별 연락처 정보 추출 패턴
        patterns = [
            r'문의\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'담당\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'연락처\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'사무처\s*:\s*([^(]+?)(?:\(([^)]+)\))?',
            r'위원회\s+사무처\s*(?:\(([^)]+)\))?',
            r'대통령직속\s+([가-힣]+위원회)\s+사무처',
            r'홈페이지\s*:\s*(https?://[^\s]+)'
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
                        if contact:
                            if 'http' in contact:
                                contact_info['website'] = contact
                            elif any(prefix in contact for prefix in ['02-', '044-', '070-']):
                                contact_info['phone'] = contact
                else:
                    if match and len(match) > 1 and len(match) < 100:
                        contact_info['department'] = match.strip()
        
        return '; '.join([f"{k}: {v}" for k, v in contact_info.items()])

    def extract_policy_keywords(self, content):
        """정책 키워드 추출"""
        # 대통령직속위원회별 정책 키워드 패턴
        policy_patterns = [
            r'(정책|제도|방안|계획|전략|로드맵|가이드라인)',
            r'(회의|논의|심의|의결|결정|합의|협의)',
            r'(발표|공표|공개|공지|안내|홍보)',
            r'(개선|강화|확대|도입|시행|추진|실시)',
            r'(협력|연계|협업|파트너십|거버넌스)',
            r'(민관|산학연|시민사회|이해관계자)',
            r'(혁신|개혁|전환|변화|발전|성장)'
        ]
        
        keywords = set()
        for pattern in policy_patterns:
            matches = re.findall(pattern, content)
            keywords.update(matches)
        
        return ', '.join(list(keywords)[:15])  # 최대 15개 키워드

    def extract_meeting_type(self, content):
        """회의/행사 유형 추출"""
        meeting_patterns = [
            r'(전체회의|본회의|실무회의)',
            r'(포럼|세미나|심포지엄|워크숍)',
            r'(토론회|간담회|공청회|설명회)',
            r'(컨퍼런스|총회|정기회의|임시회의)',
            r'(발표회|보고회|평가회|점검회의)',
            r'(협약식|서명식|출범식|개최식)'
        ]
        
        for pattern in meeting_patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0]
        
        return ''

    def extract_stakeholders(self, content):
        """이해관계자 추출"""
        stakeholder_patterns = [
            r'(정부|부처|기관|청)',
            r'(기업|업계|산업계|경제계)',
            r'(노동계|노조|근로자)',
            r'(시민사회|NGO|NPO)',
            r'(학계|연구기관|전문가)',
            r'(지방자치단체|지자체|시도)',
            r'(국제기구|해외기관)'
        ]
        
        stakeholders = set()
        for pattern in stakeholder_patterns:
            matches = re.findall(pattern, content)
            stakeholders.update(matches)
        
        return ', '.join(list(stakeholders)[:8])  # 최대 8개

    def get_committee_category(self, committee_name):
        """위원회의 카테고리 반환"""
        for category, committees in self.committee_categories.items():
            if committee_name in committees:
                return category
        return '기타'

    def get_relevant_keywords(self, committee_name, content):
        """위원회별 관련 키워드 매칭"""
        if committee_name in self.committee_keywords:
            keywords = self.committee_keywords[committee_name]
            found_keywords = []
            for keyword in keywords:
                if keyword in content:
                    found_keywords.append(keyword)
            return ', '.join(found_keywords[:10])  # 최대 10개
        return ''

    def crawl_presidential_committee_feed(self, committee, rss_url, max_items=35):
        """개별 대통령직속위원회 RSS 피드 크롤링"""
        self.logger.info(f"대통령직속위원회 크롤링 시작: {committee}")
        
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
                if item['link']:
                    article_detail = self.extract_article_content(item['link'])
                    
                    article_data = {
                        'presidential_committee': committee,
                        'committee_category': self.get_committee_category(committee),
                        'business_area': self.committee_areas.get(committee, ''),
                        'policy_direction': self.policy_directions.get(committee, ''),
                        'title': item['title'],
                        'link': item['link'],
                        'pub_date': item['pub_date'],
                        'creator': item['creator'],
                        'description': item['description'],
                        'content': article_detail['content'],
                        'contact_info': article_detail['contact_info'],
                        'policy_keywords': article_detail['policy_keywords'],
                        'meeting_type': article_detail['meeting_type'],
                        'stakeholders': article_detail['stakeholders'],
                        'relevant_keywords': self.get_relevant_keywords(committee, article_detail['content']),
                        'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    self.articles.append(article_data)
                
                # 딜레이
                self.random_delay(1, 3)
                
            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue
        
        self.logger.info(f"{committee} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_presidential_committees(self, max_items_per_committee=35):
        """모든 대통령직속위원회 RSS 피드 크롤링"""
        total_committees = len(self.presidential_committee_feeds)
        self.logger.info(f"전체 {total_committees}개 대통령직속위원회 RSS 피드 크롤링 시작")
        
        for i, (committee, rss_url) in enumerate(self.presidential_committee_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_committees}] {committee} 피드 크롤링 중...")
                self.crawl_presidential_committee_feed(committee, rss_url, max_items_per_committee)
                
                # 위원회 간 딜레이
                if i < total_committees:
                    self.random_delay(4, 7)
                    
            except Exception as e:
                self.logger.error(f"{committee} 대통령직속위원회 크롤링 오류: {e}")
                continue
        
        self.logger.info(f"전체 대통령직속위원회 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_committees(self, committee_names, max_items_per_committee=35):
        """특정 대통령직속위원회들만 크롤링"""
        for committee_name in committee_names:
            if committee_name in self.presidential_committee_feeds:
                self.crawl_presidential_committee_feed(committee_name, self.presidential_committee_feeds[committee_name], max_items_per_committee)
            else:
                self.logger.warning(f"존재하지 않는 대통령직속위원회: {committee_name}")
                available_committees = list(self.presidential_committee_feeds.keys())
                self.logger.info(f"사용 가능한 대통령직속위원회: {available_committees}")

    def crawl_by_category(self, categories, max_items_per_committee=30):
        """카테고리별 대통령직속위원회 크롤링"""
        target_committees = []
        
        for category in categories:
            if category in self.committee_categories:
                target_committees.extend(self.committee_categories[category])
            else:
                self.logger.warning(f"존재하지 않는 카테고리: {category}")
        
        if target_committees:
            self.logger.info(f"카테고리 '{', '.join(categories)}'에 해당하는 대통령직속위원회: {target_committees}")
            self.crawl_specific_committees(target_committees, max_items_per_committee)
        else:
            self.logger.warning(f"해당 카테고리에 맞는 대통령직속위원회를 찾을 수 없습니다: {categories}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'results/대통령직속위원회_RSS_{timestamp}.csv'
        
        try:
            df = pd.DataFrame(self.articles)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_committee(self):
        """대통령직속위원회별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for committee in df['presidential_committee'].unique():
            committee_df = df[df['presidential_committee'] == committee]
            filename = f'results/대통령직속_{committee}_{timestamp}.csv'
            committee_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{committee} 저장 완료: {filename} ({len(committee_df)}개 기사)")

    def save_by_category(self):
        """카테고리별로 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for category in df['committee_category'].unique():
            category_df = df[df['committee_category'] == category]
            filename = f'results/대통령직속카테고리_{category}_{timestamp}.csv'
            category_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{category} 카테고리 저장 완료: {filename} ({len(category_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return
        
        df = pd.DataFrame(self.articles)
        
        print("\n" + "="*70)
        print("대통령직속위원회별 RSS 크롤링 통계")
        print("="*70)
        
        # 대통령직속위원회별 통계
        committee_stats = df['presidential_committee'].value_counts()
        print(f"\n🏛️ 대통령직속위원회별 기사 수:")
        for committee, count in committee_stats.items():
            business_area = self.committee_areas.get(committee, '')
            policy_direction = self.policy_directions.get(committee, '')
            print(f"  • {committee}")
            print(f"    - 업무분야: {business_area}")
            print(f"    - 정책방향: {policy_direction}")
            print(f"    - 기사 수: {count}개\n")
        
        # 카테고리별 통계
        category_stats = df['committee_category'].value_counts()
        print(f"📊 카테고리별 기사 수:")
        for category, count in category_stats.items():
            print(f"  • {category}: {count}개")
        
        # 회의/행사 유형별 통계
        meeting_stats = df[df['meeting_type'] != '']['meeting_type'].value_counts().head(10)
        if not meeting_stats.empty:
            print(f"\n🤝 주요 회의/행사 유형별 기사 수:")
            for meeting_type, count in meeting_stats.items():
                print(f"  • {meeting_type}: {count}개")
        
        # 이해관계자 통계
        stakeholder_stats = df[df['stakeholders'] != '']['stakeholders'].str.split(', ').explode().value_counts().head(8)
        if not stakeholder_stats.empty:
            print(f"\n👥 주요 이해관계자별 언급 수:")
            for stakeholder, count in stakeholder_stats.items():
                print(f"  • {stakeholder}: {count}회")
        
        # 정책 키워드 통계
        policy_available = len(df[df['policy_keywords'] != ''])
        print(f"\n📋 정책 키워드:")
        print(f"  • 키워드 추출 성공: {policy_available}개")
        print(f"  • 키워드 추출 실패: {len(df) - policy_available}개")
        
        # 연락처 정보 통계
        contact_available = len(df[df['contact_info'] != ''])
        print(f"\n📞 연락처 정보:")
        print(f"  • 연락처 추출 성공: {contact_available}개")
        print(f"  • 연락처 추출 실패: {len(df) - contact_available}개")
        
        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 대통령직속위원회 수: {len(committee_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 관련 키워드 매칭: {len(df[df['relevant_keywords'] != ''])}개")
        print("="*70)

    def get_available_committees(self):
        """사용 가능한 대통령직속위원회 목록 반환"""
        return list(self.presidential_committee_feeds.keys())

    def get_categories(self):
        """카테고리 목록 반환"""
        return list(self.committee_categories.keys())


def main():
    """메인 실행 함수"""
    print("정책브리핑 대통령직속위원회별 RSS 크롤러")
    print("="*50)
    
    crawler = PresidentialCommitteeRSSCrawler()
    
    # 사용 예시 1: 전체 대통령직속위원회 크롤링 (각 위원회당 25개씩)
    print("전체 대통령직속위원회 RSS 피드 크롤링을 시작합니다...")
    crawler.crawl_all_presidential_committees(max_items_per_committee=10)
    
    # CSV 저장
    crawler.save_to_csv()
    
    # 위원회별 개별 파일 저장
    # crawler.save_by_committee()
    
    # 카테고리별 파일 저장
    # crawler.save_by_category()
    
    # 사용 예시 2: 특정 대통령직속위원회만 크롤링
    # crawler.crawl_specific_committees(['탄소중립녹색성장위원회', '경제사회노동위원회'])
    
    # 사용 예시 3: 카테고리별 크롤링
    # crawler.crawl_by_category(['환경·기후', '노동·경제'], max_items_per_committee=30)
    
    print("\n대통령직속위원회별 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
