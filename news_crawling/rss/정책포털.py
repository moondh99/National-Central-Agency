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

class KoreaPolicyRSSCrawler:
    def __init__(self):
        """정책브리핑 RSS 크롤러 초기화"""
        self.base_url = "https://www.korea.kr"
        
        # 16개 RSS 피드 정의
        self.rss_feeds = {
            '정책뉴스': 'https://www.korea.kr/rss/policy.xml',
            '국민이_말하는_정책': 'https://www.korea.kr/rss/reporter.xml',
            '기고_칼럼': 'https://www.korea.kr/rss/gigo_column.xml',
            '보도자료': 'https://www.korea.kr/rss/pressrelease.xml',
            '사실은_이렇습니다': 'https://www.korea.kr/rss/fact.xml',
            '부처_브리핑': 'https://www.korea.kr/rss/ebriefing.xml',
            '대통령실_브리핑': 'https://www.korea.kr/rss/president.xml',
            '국무회의_브리핑': 'https://www.korea.kr/rss/cabinet.xml',
            '연설문': 'https://www.korea.kr/rss/speech.xml',
            '정책자료_전문자료': 'https://www.korea.kr/rss/expdoc.xml',
            'K공감_전체': 'https://www.korea.kr/rss/archive.xml'
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
                    article_info['description'] = soup.get_text().strip()[:200] + '...' if len(soup.get_text().strip()) > 200 else soup.get_text().strip()
                else:
                    article_info['description'] = ''
                
                items.append(article_info)
            
            return items
        except Exception as e:
            self.logger.error(f"RSS 파싱 오류: {e}")
            return []

    def extract_article_content(self, article_url, max_retries=3):
        """개별 기사 본문 추출"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                response = self.session.get(article_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 본문 추출 (정책브리핑 사이트 구조에 맞게 최적화)
                content_selectors = [
                    '.article_body',  # 일반 기사
                    '.rbody',         # 브리핑 페이지
                    '.view_cont',     # 뷰 페이지
                    '.cont_body',     # 콘텐츠 본문
                    '.policy_body',   # 정책 본문
                    '.briefing_cont', # 브리핑 내용
                    '.news_cont'      # 뉴스 내용
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
                
                # 부처명/담당자 추출
                department = self.extract_department_info(content)
                
                # 텍스트 정리
                content = re.sub(r'\s+', ' ', content).strip()
                
                return {
                    'content': content[:2000] + '...' if len(content) > 2000 else content,
                    'department': department
                }
                
            except Exception as e:
                self.logger.warning(f"기사 본문 추출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(1, 3)
                else:
                    return {'content': '추출 실패', 'department': ''}

    def extract_department_info(self, content):
        """부처명/담당자 정보 추출"""
        # 정책브리핑 특성에 맞는 부처명 추출 패턴
        patterns = [
            r'문의\s*:\s*([^(]+?)(?:\(|$)',
            r'담당\s*:\s*([^(]+?)(?:\(|$)',
            r'자료제공\s*:\s*([^(]+?)(?:\(|$)',
            r'문의처\s*:\s*([^(]+?)(?:\(|$)',
            r'발표부처\s*:\s*([^(]+?)(?:\(|$)',
            r'([가-힣]+부|[가-힣]+청|[가-힣]+원|[가-힣]+실|[가-힣]+위원회)\s+[가-힣]+과',
            r'([가-힣]+부|[가-힣]+청|[가-힣]+원|[가-힣]+실|[가-힣]+위원회)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                dept = match.group(1).strip()
                # 불필요한 문자 제거
                dept = re.sub(r'[^\w가-힣\s]', '', dept).strip()
                if len(dept) > 1 and len(dept) < 50:
                    return dept
        
        return ''

    def crawl_feed(self, category, rss_url, max_items=20):
        """개별 RSS 피드 크롤링"""
        self.logger.info(f"크롤링 시작: {category}")
        
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
                        'title': item['title'],
                        'link': item['link'],
                        'pub_date': item['pub_date'],
                        'creator': item['creator'],
                        'description': item['description'],
                        'content': article_detail['content'],
                        'department': article_detail['department'],
                        'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    self.articles.append(article_data)
                
                # 딜레이
                self.random_delay(1, 3)
                
            except Exception as e:
                self.logger.error(f"기사 처리 오류: {e}")
                continue
        
        self.logger.info(f"{category} 크롤링 완료: {len(items_to_process)}개 기사 처리")

    def crawl_all_feeds(self, max_items_per_feed=20):
        """모든 RSS 피드 크롤링"""
        total_feeds = len(self.rss_feeds)
        self.logger.info(f"전체 {total_feeds}개 RSS 피드 크롤링 시작")
        
        for i, (category, rss_url) in enumerate(self.rss_feeds.items(), 1):
            try:
                self.logger.info(f"[{i}/{total_feeds}] {category} 피드 크롤링 중...")
                self.crawl_feed(category, rss_url, max_items_per_feed)
                
                # 피드 간 딜레이
                if i < total_feeds:
                    self.random_delay(2, 5)
                    
            except Exception as e:
                self.logger.error(f"{category} 피드 크롤링 오류: {e}")
                continue
        
        self.logger.info(f"전체 크롤링 완료: {len(self.articles)}개 기사 수집")
        self.print_statistics()

    def crawl_specific_feeds(self, feed_names, max_items_per_feed=20):
        """특정 RSS 피드만 크롤링"""
        for feed_name in feed_names:
            if feed_name in self.rss_feeds:
                self.crawl_feed(feed_name, self.rss_feeds[feed_name], max_items_per_feed)
            else:
                self.logger.warning(f"존재하지 않는 피드: {feed_name}")
                available_feeds = list(self.rss_feeds.keys())
                self.logger.info(f"사용 가능한 피드: {available_feeds}")

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if not self.articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'results/정책브리핑_RSS_{timestamp}.csv'
        
        try:
            df = pd.DataFrame(self.articles)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            self.logger.info(f"총 {len(self.articles)}개 기사 저장")
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")

    def print_statistics(self):
        """크롤링 통계 출력"""
        if not self.articles:
            return
        
        df = pd.DataFrame(self.articles)
        
        print("\n" + "="*60)
        print("정책브리핑 RSS 크롤링 통계")
        print("="*60)
        
        # 카테고리별 통계
        category_stats = df['category'].value_counts()
        print(f"\n📊 카테고리별 기사 수:")
        for category, count in category_stats.items():
            print(f"  • {category}: {count}개")
        
        # 부처별 통계 (상위 10개)
        dept_stats = df[df['department'] != '']['department'].value_counts().head(10)
        if not dept_stats.empty:
            print(f"\n🏛️ 주요 부처별 기사 수 (상위 10개):")
            for dept, count in dept_stats.items():
                print(f"  • {dept}: {count}개")
        
        print(f"\n📈 전체 요약:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 크롤링 카테고리: {len(category_stats)}개")
        print(f"  • 본문 추출 성공: {len(df[df['content'] != '추출 실패'])}개")
        print(f"  • 부처 정보 추출: {len(df[df['department'] != ''])}개")
        print("="*60)

    def get_available_feeds(self):
        """사용 가능한 RSS 피드 목록 반환"""
        return list(self.rss_feeds.keys())


def main():
    """메인 실행 함수"""
    print("정책브리핑(korea.kr) RSS 크롤러")
    print("="*50)
    
    crawler = KoreaPolicyRSSCrawler()
    
    # 사용 예시 1: 전체 피드 크롤링 (각 피드당 10개씩)
    print("전체 RSS 피드 크롤링을 시작합니다...")
    crawler.crawl_all_feeds(max_items_per_feed=5)
    
    # CSV 저장
    crawler.save_to_csv()
    
    # 사용 예시 2: 특정 피드만 크롤링
    # crawler.crawl_specific_feeds(['정책뉴스', '보도자료'], max_items_per_feed=20)
    
    print("\n크롤링이 완료되었습니다!")


if __name__ == "__main__":
    main()
