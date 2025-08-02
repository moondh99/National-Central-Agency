import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import csv
import time
import random
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SisaJournalRSSCrawler:
    def __init__(self):
        self.base_url = "https://www.sisajournal.com"
        self.session = requests.Session()
        
        # 다양한 User-Agent 설정
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        # 시사저널 RSS 피드 목록
        self.rss_feeds = {
            '전체기사': 'https://www.sisajournal.com/rss/allArticle.xml',
            '인기기사': 'https://www.sisajournal.com/rss/clickTop.xml',
            '사회': 'https://www.sisajournal.com/rss/S1N47.xml',
            '연예': 'https://www.sisajournal.com/rss/S1N52.xml',
            '네트워크': 'https://www.sisajournal.com/rss/S1N53.xml',
            '경제': 'https://www.sisajournal.com/rss/S1N54.xml',
            '생활': 'https://www.sisajournal.com/rss/S1N56.xml',
            'OPINION': 'https://www.sisajournal.com/rss/S1N57.xml',
            '정치': 'https://www.sisajournal.com/rss/S1N58.xml',
            '국제': 'https://www.sisajournal.com/rss/S1N59.xml',
            '포토': 'https://www.sisajournal.com/rss/S1N60.xml',
            '연예': 'https://www.sisajournal.com/rss/S1N64.xml',
            '스포츠': 'https://www.sisajournal.com/rss/S1N65.xml'
        }
        
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_random_user_agent(self):
        return random.choice(self.user_agents)

    def safe_request(self, url, max_retries=3):
        """안전한 요청 처리"""
        for attempt in range(max_retries):
            try:
                self.session.headers['User-Agent'] = self.get_random_user_agent()
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"요청 실패 (시도 {attempt + 1}/{max_retries}): {url} - {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                else:
                    logger.error(f"최대 재시도 초과: {url}")
                    return None

    def parse_rss_feed(self, rss_url):
        """RSS 피드 파싱"""
        logger.info(f"RSS 피드 파싱 중: {rss_url}")
        
        response = self.safe_request(rss_url)
        if not response:
            return []
        
        try:
            # UTF-8로 디코딩
            content = response.content.decode('utf-8')
            root = ET.fromstring(content)
            
            articles = []
            items = root.findall('.//item')
            
            for item in items:
                try:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    pubdate_elem = item.find('pubDate')
                    description_elem = item.find('description')
                    
                    if title_elem is not None and link_elem is not None:
                        title = title_elem.text.strip() if title_elem.text else ""
                        link = link_elem.text.strip() if link_elem.text else ""
                        pubdate = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""
                        description = description_elem.text.strip() if description_elem is not None and description_elem.text else ""
                        
                        # 시사저널 특화: description에서 기자명 추출
                        reporter = self.extract_reporter_from_description(description)
                        
                        articles.append({
                            'title': title,
                            'link': link,
                            'pubdate': pubdate,
                            'description': description,
                            'reporter': reporter
                        })
                        
                except Exception as e:
                    logger.warning(f"RSS 아이템 파싱 오류: {str(e)}")
                    continue
            
            logger.info(f"RSS에서 {len(articles)}개 기사 발견")
            return articles
            
        except ET.ParseError as e:
            logger.error(f"RSS XML 파싱 오류: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"RSS 파싱 중 오류: {str(e)}")
            return []

    def extract_reporter_from_description(self, description):
        """description에서 기자명 추출"""
        if not description:
            return ""
        
        # 시사저널 특화 기자명 패턴들
        patterns = [
            r'([가-힣]{2,4})\s*기자',
            r'([가-힣]{2,4})\s*특파원',
            r'([가-힣]{2,4})\s*대표',
            r'([가-힣]{2,4})\s*원장',
            r'([가-힣]{2,4})\s*교수',
            r'([가-힣]{2,4})\s*연구위원',
            r'([가-힣]{2,4})\s*논설위원',
            r'([가-힣]{2,4})\s*편집위원',
            r'\/\s*([가-힣]{2,4})',  # "/ 김철수" 형태
            r'([가-힣]{2,4})\s*\/',  # "김철수 /" 형태
            r'\[([가-힣]{2,4})\]',   # "[김철수]" 형태
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        
        return ""

    def extract_article_content(self, article_url):
        """기사 본문 및 기자명 추출 - 시사저널 특화"""
        logger.info(f"기사 내용 추출 중: {article_url}")
        
        response = self.safe_request(article_url)
        if not response:
            return "", ""
        
        try:
            # 응답 인코딩 설정
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 기사 본문 추출 - 시사저널 전용 선택자들
            content = ""
            
            # 시사저널의 실제 본문 선택자들 (우선순위 순)
            content_selectors = [
                '#article-view-content-div',  # 메인 본문 컨테이너
                '.article-content',
                '.view-content', 
                '#articleText',
                '.news-content',
                '.content',
                'div[itemprop="articleBody"]',
                '.article_view',
                '.article-body'
            ]
            
            article_content = None
            for selector in content_selectors:
                article_content = soup.select_one(selector)
                if article_content:
                    logger.info(f"본문을 찾았습니다: {selector}")
                    break
            
            # 본문을 찾지 못한 경우, 더 넓은 범위에서 찾기
            if not article_content:
                # 기사 제목을 찾아서 그 이후의 모든 텍스트를 본문으로 간주
                title_selectors = [
                    'h1.article-title',
                    'h1.title',
                    'h1',
                    'h2',
                    '.title'
                ]
                
                title_elem = None
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        break
                
                if title_elem:
                    # 제목 이후의 모든 p 태그들을 본문으로 간주
                    next_elem = title_elem.find_next_sibling()
                    content_parts = []
                    
                    # 제목 다음 요소부터 순회하며 본문 수집
                    current = title_elem.parent
                    paragraphs = current.find_all('p')
                    
                    for p in paragraphs:
                        p_text = p.get_text(strip=True)
                        if p_text and len(p_text) > 20:  # 의미있는 길이의 텍스트만
                            content_parts.append(p_text)
                    
                    content = ' '.join(content_parts)
                
                # 여전히 본문이 없으면 전체 텍스트에서 추출
                if not content:
                    all_text = soup.get_text()
                    # 제목을 찾아서 그 이후 텍스트를 본문으로 사용
                    title_text = soup.find('h1')
                    if title_text:
                        title_text = title_text.get_text(strip=True)
                        if title_text in all_text:
                            content_start = all_text.find(title_text) + len(title_text)
                            content = all_text[content_start:].strip()
            else:
                # 본문 컨테이너를 찾은 경우
                # 불필요한 태그 제거
                for tag in article_content.find_all(['script', 'style', 'iframe', 'embed', 'noscript']):
                    tag.decompose()
                
                # 이미지 캡션 제거
                for tag in article_content.find_all(['figcaption', '.caption', '.photo-caption']):
                    tag.decompose()
                
                # 광고 관련 요소 제거
                for tag in article_content.find_all(['div'], class_=re.compile('ad|banner|광고')):
                    tag.decompose()
                
                # 관련기사, 태그 등 제거
                for tag in article_content.find_all(['div', 'span'], class_=re.compile('tag|related|sns|share')):
                    tag.decompose()
                
                # 텍스트 추출
                content = article_content.get_text(separator=' ', strip=True)
            
            # 텍스트 정리
            if content:
                content = re.sub(r'\s+', ' ', content)
                content = content.replace('\n', ' ').replace('\r', ' ')
                # 너무 짧은 경우 (헤더/푸터만 추출된 경우) 제외
                if len(content) < 100:
                    content = ""
            
            # 기자명 추출
            reporter = ""
            
            # 1. 기자명 전용 요소에서 추출
            reporter_selectors = [
                '.writer',
                '.reporter', 
                '.byline',
                '.author',
                '.article-author',
                '.news-author',
                '.journalist',
                '.editor'
            ]
            
            for selector in reporter_selectors:
                reporter_elem = soup.select_one(selector)
                if reporter_elem:
                    reporter_text = reporter_elem.get_text(strip=True)
                    match = re.search(r'([가-힣]{2,4})\s*(?:기자|특파원|논설위원|편집위원)', reporter_text)
                    if match:
                        reporter = match.group(1)
                        break
            
            # 2. 본문에서 기자명 추출 시도
            if not reporter and content:
                # 본문 첫 부분에서 기자명 찾기
                first_200_chars = content[:200]
                match = re.search(r'([가-힣]{2,4})\s*(?:기자|특파원|논설위원|편집위원)', first_200_chars)
                if match:
                    reporter = match.group(1)
                
                # 본문 끝 부분에서 기자명 찾기
                if not reporter:
                    last_200_chars = content[-200:]
                    match = re.search(r'([가-힣]{2,4})\s*(?:기자|특파원|논설위원|편집위원)', last_200_chars)
                    if match:
                        reporter = match.group(1)
            
            # 3. 전체 페이지에서 기자명 찾기
            if not reporter:
                page_text = soup.get_text()
                # 시사저널 특화 패턴
                patterns = [
                    r'([가-힣]{2,4})\s*기자',
                    r'([가-힣]{2,4})\s*특파원',
                    r'([가-힣]{2,4})\s*논설위원',
                    r'([가-힣]{2,4})\s*편집위원',
                    r'글\s*([가-힣]{2,4})',
                    r'정리\s*([가-힣]{2,4})',
                    r'취재\s*([가-힣]{2,4})'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        reporter = match.group(1)
                        break
            
            logger.info(f"본문 추출 완료: {len(content)}자, 기자: {reporter}")
            return content, reporter
            
        except Exception as e:
            logger.error(f"기사 내용 추출 오류: {str(e)}")
            return "", ""

    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return ""
        
        try:
            # RSS 날짜 형식 파싱
            if ',' in date_str:
                date_part = date_str.split(',', 1)[1].strip()
                # "+0900" 제거
                if '+' in date_part:
                    date_part = date_part.split('+')[0].strip()
                elif '-' in date_part and date_part.count('-') > 2:
                    date_part = date_part.rsplit('-', 1)[0].strip()
                
                # 날짜 파싱 시도
                try:
                    parsed_date = datetime.strptime(date_part, "%d %b %Y %H:%M:%S")
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            
            # 다른 형식들 시도
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%d %b %Y %H:%M:%S",
                "%a, %d %b %Y %H:%M:%S"
            ]
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str.strip(), fmt)
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            return date_str.strip()
            
        except Exception as e:
            logger.warning(f"날짜 파싱 오류: {date_str} - {str(e)}")
            return date_str

    def crawl_category(self, category_name, rss_url, max_articles=None):
        """특정 카테고리 크롤링"""
        logger.info(f"=== {category_name} 카테고리 크롤링 시작 ===")
        
        # RSS 피드에서 기사 목록 가져오기
        articles = self.parse_rss_feed(rss_url)
        
        if max_articles:
            articles = articles[:max_articles]
        
        crawled_articles = []
        
        for i, article in enumerate(articles, 1):
            logger.info(f"기사 {i}/{len(articles)} 처리 중: {article['title'][:50]}...")
            
            try:
                # 기사 본문 추출
                content, page_reporter = self.extract_article_content(article['link'])
                
                # 기자명 결정 (페이지 > RSS description)
                final_reporter = page_reporter if page_reporter else article['reporter']
                
                crawled_article = {
                    'category': category_name,
                    'title': article['title'],
                    'date': self.parse_date(article['pubdate']),
                    'reporter': final_reporter,
                    'content': content,
                    'url': article['link']
                }
                
                crawled_articles.append(crawled_article)
                
                # 서버 부하 방지를 위한 딜레이
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"기사 처리 오류: {article['link']} - {str(e)}")
                continue
        
        logger.info(f"=== {category_name} 카테고리 완료: {len(crawled_articles)}개 기사 ===")
        return crawled_articles

    def save_to_csv(self, articles, filename):
        """CSV 파일로 저장"""
        if not articles:
            logger.warning("저장할 기사가 없습니다.")
            return
        
        logger.info(f"CSV 파일 저장 중: {filename}")
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['category', 'title', 'date', 'reporter', 'content', 'url']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for article in articles:
                    writer.writerow(article)
            
            logger.info(f"CSV 저장 완료: {filename} ({len(articles)}개 기사)")
            
        except Exception as e:
            logger.error(f"CSV 저장 오류: {str(e)}")

    def crawl_all_categories(self, max_articles_per_category=None):
        """모든 카테고리 크롤링"""
        logger.info("=== 시사저널 전체 카테고리 크롤링 시작 ===")
        
        all_articles = []
        
        for category_name, rss_url in self.rss_feeds.items():
            try:
                category_articles = self.crawl_category(category_name, rss_url, max_articles_per_category)
                all_articles.extend(category_articles)
                
                # 카테고리 간 딜레이
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"{category_name} 카테고리 크롤링 오류: {str(e)}")
                continue
        
        logger.info(f"=== 전체 크롤링 완료: {len(all_articles)}개 기사 ===")
        return all_articles

    def crawl_specific_categories(self, categories, max_articles_per_category=None):
        """특정 카테고리들만 크롤링"""
        logger.info(f"=== 선택된 카테고리 크롤링 시작: {categories} ===")
        
        all_articles = []
        
        for category_name in categories:
            if category_name in self.rss_feeds:
                try:
                    rss_url = self.rss_feeds[category_name]
                    category_articles = self.crawl_category(category_name, rss_url, max_articles_per_category)
                    all_articles.extend(category_articles)
                    
                    # 카테고리 간 딜레이
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    logger.error(f"{category_name} 카테고리 크롤링 오류: {str(e)}")
                    continue
            else:
                logger.warning(f"존재하지 않는 카테고리: {category_name}")
        
        logger.info(f"=== 선택된 카테고리 크롤링 완료: {len(all_articles)}개 기사 ===")
        return all_articles


def main():
    """메인 실행 함수"""
    crawler = SisaJournalRSSCrawler()
    
    print("시사저널 RSS 크롤러")
    print("=" * 50)
    print("사용 가능한 카테고리:")
    for i, category in enumerate(crawler.rss_feeds.keys(), 1):
        print(f"{i:2d}. {category}")
    
    print("\n크롤링 옵션:")
    print("1. 전체 카테고리 크롤링")
    print("2. 특정 카테고리 선택")
    print("3. 주요 카테고리만 (전체기사, 정치, 경제, 사회, OPINION)")
    
    try:
        choice = input("\n선택하세요 (1-3): ").strip()
        
        max_articles = input("카테고리별 최대 기사 수 (기본값: 모두, 숫자 입력 시 제한): ").strip()
        max_articles = int(max_articles) if max_articles.isdigit() else None
        
        if choice == "1":
            # 전체 카테고리 크롤링
            articles = crawler.crawl_all_categories(max_articles)
            filename = f"results/sisajournal_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        elif choice == "2":
            # 특정 카테고리 선택
            selected = input("크롤링할 카테고리를 번호로 입력하세요 (쉼표로 구분, 예: 1,3,5): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in selected.split(',')]
                category_names = list(crawler.rss_feeds.keys())
                selected_categories = [category_names[i] for i in indices if 0 <= i < len(category_names)]
                
                if not selected_categories:
                    print("올바른 카테고리를 선택해주세요.")
                    return
                
                articles = crawler.crawl_specific_categories(selected_categories, max_articles)
                filename = f"results/sisajournal_selected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
            except (ValueError, IndexError):
                print("올바른 번호를 입력해주세요.")
                return
        
        elif choice == "3":
            # 주요 카테고리만
            main_categories = ['전체기사', '정치', '경제', '사회', 'OPINION']
            articles = crawler.crawl_specific_categories(main_categories, max_articles)
            filename = f"results/sisajournal_main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:
            print("올바른 옵션을 선택해주세요.")
            return
        
        # 결과 저장
        if articles:
            crawler.save_to_csv(articles, filename)
            print(f"\n크롤링 완료!")
            print(f"저장된 파일: {filename}")
            print(f"총 기사 수: {len(articles)}")
            
            # 카테고리별 통계
            from collections import Counter
            category_stats = Counter(article['category'] for article in articles)
            print(f"\n카테고리별 기사 수:")
            for category, count in category_stats.items():
                print(f"  {category}: {count}개")
        else:
            print("크롤링된 기사가 없습니다.")
    
    except KeyboardInterrupt:
        print("\n\n크롤링이 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")


if __name__ == "__main__":
    main()
