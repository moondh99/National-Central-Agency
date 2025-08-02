#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
에이블뉴스(ablenews.co.kr) RSS 크롤링 코드
13개 카테고리 RSS 피드 지원하는 장애인 전문 언론사 크롤러

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

class AbleNewsRSSCrawler:
    def __init__(self):
        """에이블뉴스 RSS 크롤러 초기화"""
        self.base_url = "https://www.ablenews.co.kr"
        
        # 13개 에이블뉴스 RSS 피드
        self.rss_feeds = {
            '전체기사': 'https://www.ablenews.co.kr/rss/allArticle.xml',
            '인기기사': 'https://www.ablenews.co.kr/rss/clickTop.xml',
            '정보세상': 'https://www.ablenews.co.kr/rss/S1N1.xml',
            '오피니언': 'https://www.ablenews.co.kr/rss/S1N2.xml',
            '인권': 'https://www.ablenews.co.kr/rss/S1N3.xml',
            '노동': 'https://www.ablenews.co.kr/rss/S1N4.xml',
            '교육': 'https://www.ablenews.co.kr/rss/S1N5.xml',
            '복지': 'https://www.ablenews.co.kr/rss/S1N6.xml',
            '자립생활': 'https://www.ablenews.co.kr/rss/S1N7.xml',
            '문화/체육': 'https://www.ablenews.co.kr/rss/S1N8.xml',
            '단체': 'https://www.ablenews.co.kr/rss/S1N9.xml',
            '전국넷': 'https://www.ablenews.co.kr/rss/S1N10.xml',
            '정책': 'https://www.ablenews.co.kr/rss/S1N11.xml',
            '동영상': 'https://www.ablenews.co.kr/rss/S1N12.xml',
            '기획특집': 'https://www.ablenews.co.kr/rss/S1N14.xml'
        }
        
        # 카테고리별 설명
        self.category_descriptions = {
            '전체기사': '에이블뉴스 전체 기사',
            '인기기사': '조회수가 높은 인기 기사',
            '정보세상': '장애인 생활 정보 및 유용한 정보',
            '오피니언': '칼럼, 사설, 논평 등 의견글',
            '인권': '장애인 인권 관련 이슈',
            '노동': '장애인 고용 및 노동 관련 소식',
            '교육': '장애인 교육 정책 및 현황',
            '복지': '장애인 복지 제도 및 서비스',
            '자립생활': '장애인 자립생활 지원 및 사례',
            '문화/체육': '장애인 문화활동 및 체육 소식',
            '단체': '장애인 단체 및 기관 활동',
            '전국넷': '전국 각 지역의 장애인 관련 소식',
            '정책': '장애인 관련 정부 정책',
            '동영상': '동영상 뉴스 및 콘텐츠',
            '기획특집': '심층 보도 및 특집 기사'
        }
        
        # 카테고리 그룹 분류
        self.category_groups = {
            '권익·인권': ['인권', '정책'],
            '생활·복지': ['정보세상', '복지', '자립생활'],
            '사회·노동': ['노동', '교육'],
            '문화·활동': ['문화/체육', '단체', '전국넷'],
            '특별·기획': ['오피니언', '동영상', '기획특집'],
            '종합': ['전체기사', '인기기사']
        }
        
        # 장애 관련 키워드
        self.disability_keywords = [
            '시각장애', '청각장애', '지체장애', '뇌병변장애', '발달장애', '지적장애',
            '정신장애', '신장장애', '심장장애', '호흡기장애', '간장애', '안면장애',
            '장루·요루장애', '뇌전증장애', '자폐성장애', '중증장애', '경증장애'
        ]
        
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
            'Referer': 'https://www.ablenews.co.kr/'
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
        """개별 기사 본문 추출 - 에이블뉴스 페이지 최적화"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 에이블뉴스 페이지 구조에 최적화된 본문 추출 셀렉터
                content_selectors = [
                    '.news_content',        # 뉴스 본문
                    '.article_content',     # 기사 내용
                    '.view_content',        # 뷰 내용
                    '.detail_content',      # 상세 내용
                    '.news_text',          # 뉴스 텍스트
                    '.content_area',       # 콘텐츠 영역
                    '.article_body',       # 기사 본문
                    '.news_body',          # 뉴스 본문
                    '#article-view-content-div'  # 특정 ID
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
                
                # 기자명 추출
                reporter = self.extract_reporter_name(soup, content)
                
                # 장애 유형 추출
                disability_types = self.extract_disability_types(content)
                
                # 관련 기관/단체 추출
                organizations = self.extract_organizations(content)
                
                # 텍스트 정리
                content = re.sub(r'\s+', ' ', content).strip()
                
                return {
                    'content': content[:3000] + '...' if len(content) > 3000 else content,
                    'reporter': reporter,
                    'disability_types': disability_types,
                    'organizations': organizations
                }
                
            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {'content': '추출 실패', 'reporter': '', 'disability_types': '', 'organizations': ''}

    def extract_reporter_name(self, soup, content):
        """기자명 추출"""
        # 에이블뉴스 기자명 추출 패턴
        reporter_patterns = [
            r'기자\s*([가-힣]{2,4})\s*기자',
            r'([가-힣]{2,4})\s*기자',
            r'기자\s*:\s*([가-힣]{2,4})',
            r'취재\s*:\s*([가-힣]{2,4})',
            r'글\s*:\s*([가-힣]{2,4})',
            r'작성자\s*:\s*([가-힣]{2,4})'
        ]
        
        # HTML에서 기자명 찾기
        reporter_selectors = [
            '.reporter_name',
            '.author_name',
            '.writer_name',
            '.byline'
        ]
        
        for selector in reporter_selectors:
            reporter_elem = soup.select_one(selector)
            if reporter_elem:
                return reporter_elem.get_text().strip()
        
        # 텍스트에서 기자명 패턴 매칭
        for pattern in reporter_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return ''

    def extract_disability_types(self, content):
        """장애 유형 추출"""
        found_types = []
        for disability_type in self.disability_keywords:
            if disability_type in content:
                found_types.append(disability_type)
        
        return ', '.join(found_types[:5])  # 최대 5개

    def extract_organizations(self, content):
        """관련 기관/단체 추출"""
        org_patterns = [
            r'([가-힣]+장애인[가-힣]*단체|[가-힣]+장애인[가-힣]*협회)',
            r'([가-힣]+복지관|[가-힣]+재활원)',
            r'(보건복지부|교육부|고용노동부)',
            r'([가-힣]+시|[가-힣]+구|[가-힣]+군)\s*(청|청사)',
            r'([가-힣]+대학교|[가-힣]+대학)',
            r'([가-힣]*장애인[가-힣]*센터)'
        ]
        
        organizations = set()
        for pattern in org_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    organizations.add(match[0])
                else:
                    organizations.add(match)
        
        return ', '.join(list(organizations)[:8])  # 최대 8개

    def get_category_group(self, category_name):
        """카테고리의 그룹 반환"""
        for group, categories in self.category_groups.items():
            if category_name in categories:
                return group
        return '기타'

    def crawl_category_feed(self, category, rss_url, max_items=30):
        """개별 카테고리 RSS 피드 크롤링"""
        self.logger.info(f"에이블뉴스 카테고리 크롤링 시작: {category}")
        
        # RSS 피드 가져오기
        rss_content = self.fetch_rss_feed(rss_url)
        if not rss_content:
            return
        
        # RSS 파싱
        rss_items = self.parse_rss_feed(rss_content)
        if not rss_items:
            self.logger.warning(f"RSS 아이템이 없습니다: {category}")
            return
        
        # 지정된 개수만큼만 처리
        items_to_process = rss_items[:max_items]
        
        for i, item in enumerate(items_to_process, 1):
            try:
                self.logger.info(f"{category} 기사 처리 중: {i}/{len(items_to_process)} - {item['title'][:50]}...")
                
                # 기사 상세 내용 추출
                if item['link']:
                    article_detail = self.extract_article_content(item['link'])
                    
                    article_data = {
                        'category': category,
                        'category_group': self.get_category_group(category),
                        'category_description': self.category_descriptions.get(category, ''),
                        'title': item['title'],
                        'link': item['link'],
                        'pub_date': item['pub_date'],
                        'description': item['description'],
                        'content': article_detail['content'],
                        'reporter': article_detail['reporter'],
                        'disability_types': article_detail['disability_types'],
                        'organizations': article_detail['organizations'],
                        'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    self.articles.append(article_data)
                
                # 딜레이
                self.random_delay(1, 3)
                
            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue
        
        self.logger.info(f"{category} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_categories(self, max_items_per_category=30):
        """모든 카테고리 RSS 피드 크롤링"""
        total_categories = len(self.rss_feeds)
        self.logger.info(f"전체 {total_categories}개 에이블뉴스 카테고리 RSS 피드 크롤링 시작")
        
        for i, (category, rss_url) in enumerate(self.rss_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_categories}] {category} 피드 크롤링 중...")
                self.crawl_category_feed(category, rss_url, max_items_per_category)
                
                # 카테고리 간 딜레이
                if i < total_categories:
                    self.random_delay(2, 4)
                    
            except Exception as e:
                self.logger.error(f"{category} 카테고리 크롤링 오류: {e}")
                continue
        
        self.logger.info(f"전체 에이블뉴스 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_categories(self, category_names, max_items_per_category=30):
        """특정 카테고리들만 크롤링"""
        for category_name in category_names:
            if category_name in self.rss_feeds:
                self.crawl_category_feed(category_name, self.rss_feeds[category_name], max_items_per_category)
            else:
                self.logger.warning(f"존재하지 않는 카테고리: {category_name}")
                available_categories = list(self.rss_feeds.keys())
                self.logger.info(f"사용 가능한 카테고리: {available_categories}")

    def crawl_by_group(self, groups, max_items_per_category=25):
        """그룹별 카테고리 크롤링"""
        target_categories = []
        
        for group in groups:
            if group in self.category_groups:
                target_categories.extend(self.category_groups[group])
            else:
                self.logger.warning(f"존재하지 않는 그룹: {group}")
        
        if target_categories:
            self.logger.info(f"그룹 '{', '.join(groups)}'에 해당하는 카테고리: {target_categories}")
            self.crawl_specific_categories(target_categories, max_items_per_category)
        else:
            self.logger.warning(f"해당 그룹에 맞는 카테고리를 찾을 수 없습니다: {groups}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'results/에이블뉴스_RSS_{timestamp}.csv'
        
        try:
            df = pd.DataFrame(self.articles)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def save_by_category(self):
        """카테고리별로 개별 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for category in df['category'].unique():
            category_df = df[df['category'] == category]
            filename = f'results/에이블뉴스_{category}_{timestamp}.csv'
            category_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{category} 저장 완료: {filename} ({len(category_df)}개 기사)")

    def save_by_group(self):
        """그룹별로 CSV 파일 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        df = pd.DataFrame(self.articles)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for group in df['category_group'].unique():
            group_df = df[df['category_group'] == group]
            filename = f'results/에이블뉴스그룹_{group}_{timestamp}.csv'
            group_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"{group} 그룹 저장 완료: {filename} ({len(group_df)}개 기사)")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return
        
        df = pd.DataFrame(self.articles)
        
        print("\n" + "="*60)
        print("에이블뉴스 RSS 크롤링 통계")
        print("="*60)
        
        # 카테고리별 통계
        category_stats = df['category'].value_counts()
        print(f"\n📰 카테고리별 기사 수:")
        for category, count in category_stats.items():
            description = self.category_descriptions.get(category, '')
            print(f"  • {category} ({description}): {count}개")
        
        # 그룹별 통계
        group_stats = df['category_group'].value_counts()
        print(f"\n📊 그룹별 기사 수:")
        for group, count in group_stats.items():
            print(f"  • {group}: {count}개")
        
        # 장애 유형별 통계
        disability_stats = df[df['disability_types'] != '']['disability_types'].str.split(', ').explode().value_counts().head(10)
        if not disability_stats.empty:
            print(f"\n♿ 주요 장애 유형별 언급 수:")
            for disability_type, count in disability_stats.items():
                print(f"  • {disability_type}: {count}회")
        
        # 기자별 통계
        reporter_stats = df[df['reporter'] != '']['reporter'].value_counts().head(10)
        if not reporter_stats.empty:
            print(f"\n✍️ 주요 기자별 기사 수:")
            for reporter, count in reporter_stats.items():
                print(f"  • {reporter}: {count}개")
        
        # 관련 기관/단체 통계
        org_stats = df[df['organizations'] != '']['organizations'].str.split(', ').explode().value_counts().head(8)
        if not org_stats.empty:
            print(f"\n🏢 주요 관련 기관/단체:")
            for org, count in org_stats.items():
                print(f"  • {org}: {count}회")
        
        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 카테고리 수: {len(category_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 기자명 추출: {len(df[df['reporter'] != ''])}개")
        print(f"  • 장애 유형 매칭: {len(df[df['disability_types'] != ''])}개")
        print(f"  • 관련 기관 추출: {len(df[df['organizations'] != ''])}개")
        print("="*60)

    def get_available_categories(self):
        """사용 가능한 카테고리 목록 반환"""
        return list(self.rss_feeds.keys())

    def get_groups(self):
        """그룹 목록 반환"""
        return list(self.category_groups.keys())


def main():
    """메인 실행 함수"""
    print("에이블뉴스 RSS 크롤러")
    print("="*50)
    
    crawler = AbleNewsRSSCrawler()
    
    # 사용 예시 1: 전체 카테고리 크롤링 (각 카테고리당 20개씩)
    print("전체 에이블뉴스 RSS 피드 크롤링을 시작합니다...")
    crawler.crawl_all_categories(max_items_per_category=20)
    
    # CSV 저장
    crawler.save_to_csv()
    
    # 카테고리별 개별 파일 저장
    # crawler.save_by_category()
    
    # 그룹별 파일 저장
    # crawler.save_by_group()
    
    # 사용 예시 2: 특정 카테고리만 크롤링
    # crawler.crawl_specific_categories(['인권', '복지', '정책'])
    
    # 사용 예시 3: 그룹별 크롤링
    # crawler.crawl_by_group(['권익·인권', '생활·복지'], max_items_per_category=25)
    
    print("\n에이블뉴스 크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
