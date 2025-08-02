import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging

class KsilboRSSCollector:
    def __init__(self):
        self.base_url = "https://www.ksilbo.co.kr"
        self.rss_urls = {
            "전체기사": "https://www.ksilbo.co.kr/rss/allArticle.xml",
            "인기기사": "https://www.ksilbo.co.kr/rss/clickTop.xml",
            "정치": "https://www.ksilbo.co.kr/rss/S1N1.xml",
            "경제": "https://www.ksilbo.co.kr/rss/S1N2.xml",
            "사회": "https://www.ksilbo.co.kr/rss/S1N3.xml",
            "문화": "https://www.ksilbo.co.kr/rss/S1N4.xml",
            "체육": "https://www.ksilbo.co.kr/rss/S1N5.xml",
            "국제": "https://www.ksilbo.co.kr/rss/S1N6.xml",
            "정보통신": "https://www.ksilbo.co.kr/rss/S1N7.xml",
            "오피니언": "https://www.ksilbo.co.kr/rss/S1N8.xml"
        }
        
        # User-Agent 리스트 (랜덤 선택용)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ksilbo_rss.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_random_headers(self):
        """랜덤 User-Agent가 포함된 헤더 반환"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def extract_article_content(self, article_url):
        """기사 본문과 기자 정보 추출"""
        try:
            response = requests.get(article_url, headers=self.get_random_headers(), timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 기사 본문 추출 - 경상일보의 구조 분석
            content = ""
            
            # 전체 페이지 텍스트에서 본문 추출
            page_text = soup.get_text()
            
            # 기사 본문의 시작과 끝 패턴 찾기
            # 경상일보는 이미지 다음에 바로 본문이 시작되고, 기자 정보로 끝남
            
            # 본문 시작점 찾기 (이미지나 제목 이후)
            start_patterns = [
                r'울산시가.*?한다\.',  # 첫 문장 패턴
                r'이번.*?진행된다\.',
                r'프로그램은.*?준비된다\.',
                r'[가-힣]+시.*?[한다|된다|있다]\.'
            ]
            
            # 기자 정보 위치 찾기 (본문 끝)
            end_patterns = [
                r'([가-힣]{2,4})기자\s+[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                r'([가-힣]{2,4})\s*기자',
                r'기자\s+([가-힣]{2,4})',
                r'([가-힣]{2,4})\s*특파원'
            ]
            
            # 기자 정보 추출
            reporter = ""
            reporter_email = ""
            
            for pattern in end_patterns:
                match = re.search(pattern, page_text)
                if match:
                    reporter = match.group(1)
                    # 이메일도 함께 찾기
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 
                                          page_text[max(0, match.start()-50):match.end()+50])
                    if email_match:
                        reporter_email = email_match.group()
                    break
            
            # 본문 추출 (기자 정보 이전까지)
            if reporter:
                # 기자 정보가 있는 위치를 찾아서 그 이전까지를 본문으로 처리
                reporter_pos = page_text.find(f"{reporter}기자")
                if reporter_pos > 0:
                    content = page_text[:reporter_pos].strip()
                else:
                    content = page_text
            else:
                content = page_text
            
            # 불필요한 텍스트 제거
            unwanted_patterns = [
                r'경상일보.*?ksilbo\.co\.kr',
                r'^\s*울산시.*?정원.*?체험교실.*?운영\s*$',  # 제목 제거
                r'저작권자.*?무단전재.*?재배포.*?금지',
                r'개의\s*댓글',
                r'댓글\s*정렬',
                r'BEST댓글.*?자동으로\s*노출됩니다\.',
                r'댓글삭제.*?삭제하시겠습니까\?',
                r'댓글수정.*?가능합니다\.',
                r'홈.*?정치.*?경제.*?사회.*?문화',  # 네비게이션
                r'^\s*경상일보\s*$',
                r'^\s*울산지역.*?신문매체\.\s*$'
            ]
            
            for pattern in unwanted_patterns:
                content = re.sub(pattern, '', content, flags=re.MULTILINE | re.IGNORECASE)
            
            # 텍스트 정제
            content = re.sub(r'\s+', ' ', content)  # 연속된 공백 정리
            content = re.sub(r'\n+', '\n', content)  # 연속된 줄바꿈 정리
            content = content.strip()
            
            # 첫 번째 완전한 문장부터 시작하도록 조정
            sentences = re.split(r'[.!?]', content)
            if len(sentences) > 1:
                # 첫 문장이 너무 짧으면(메타데이터일 가능성) 제거
                if len(sentences[0]) < 10:
                    content = '.'.join(sentences[1:]).strip()
                    if content.startswith('.'):
                        content = content[1:].strip()
            
            return content, reporter
            
        except Exception as e:
            self.logger.error(f"기사 내용 추출 실패 - {article_url}: {str(e)}")
            return "", ""

    def collect_rss_data(self, category="전체기사", max_articles=50):
        """RSS 데이터 수집"""
        rss_url = self.rss_urls.get(category, self.rss_urls["전체기사"])
        self.logger.info(f"RSS 수집 시작: {category} - {rss_url}")
        
        try:
            # RSS 피드 파싱
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                self.logger.warning(f"RSS 피드에서 데이터를 찾을 수 없습니다: {rss_url}")
                return []
            
            articles = []
            
            for i, entry in enumerate(feed.entries[:max_articles]):
                try:
                    self.logger.info(f"기사 처리 중 {i+1}/{min(len(feed.entries), max_articles)}: {entry.title}")
                    
                    # 기본 정보 추출
                    title = entry.title if hasattr(entry, 'title') else ""
                    link = entry.link if hasattr(entry, 'link') else ""
                    
                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, 'published'):
                        try:
                            pub_date = entry.published
                        except:
                            pub_date = ""
                    
                    # 기사 본문 및 기자 정보 추출
                    content, reporter = self.extract_article_content(link)
                    
                    # 요약 (첫 200자)
                    summary = content[:200] + "..." if len(content) > 200 else content
                    
                    article_data = {
                        'category': category,
                        'title': title,
                        'link': link,
                        'pub_date': pub_date,
                        'reporter': reporter,
                        'summary': summary,
                        'content': content,
                        'collected_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    articles.append(article_data)
                    
                    # 요청 간격 조절 (서버 부하 방지)
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    self.logger.error(f"개별 기사 처리 실패: {str(e)}")
                    continue
            
            self.logger.info(f"RSS 데이터 수집 완료: {len(articles)}개 기사")
            return articles
            
        except Exception as e:
            self.logger.error(f"RSS 피드 파싱 실패: {str(e)}")
            return []

    def save_to_csv(self, articles, filename=None):
        """CSV 파일로 저장"""
        if not articles:
            self.logger.warning("저장할 기사가 없습니다.")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'results/ksilbo_articles_{timestamp}.csv'
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['category', 'title', 'link', 'pub_date', 'reporter', 'summary', 'content', 'collected_date']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for article in articles:
                    writer.writerow(article)
            
            self.logger.info(f"CSV 파일 저장 완료: {filename}")
            
        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {str(e)}")

    def collect_all_categories(self, max_articles_per_category=30):
        """모든 카테고리의 기사 수집"""
        all_articles = []
        
        for category in self.rss_urls.keys():
            self.logger.info(f"카테고리 '{category}' 수집 시작")
            articles = self.collect_rss_data(category, max_articles_per_category)
            all_articles.extend(articles)
            
            # 카테고리 간 대기 시간
            time.sleep(random.uniform(2, 5))
        
        return all_articles

def main():
    collector = KsilboRSSCollector()
    
    print("=== 경상일보 RSS 수집기 ===")
    print("1. 전체기사 수집")
    print("2. 인기기사 수집")
    print("3. 정치 수집")
    print("4. 경제 수집")
    print("5. 사회 수집")
    print("6. 문화 수집")
    print("7. 체육 수집")
    print("8. 국제 수집")
    print("9. 정보통신 수집")
    print("10. 오피니언 수집")
    print("11. 모든 카테고리 수집")
    
    choice = input("선택하세요 (1-11): ").strip()
    
    categories = {
        "1": "전체기사",
        "2": "인기기사",
        "3": "정치",
        "4": "경제",
        "5": "사회",
        "6": "문화",
        "7": "체육",
        "8": "국제",
        "9": "정보통신",
        "10": "오피니언"
    }
    
    if choice in categories:
        articles = collector.collect_rss_data(categories[choice], 50)
        collector.save_to_csv(articles)
    elif choice == "11":
        articles = collector.collect_all_categories(30)
        collector.save_to_csv(articles)
    else:
        print("잘못된 선택입니다.")
        return
    
    print(f"수집 완료: 총 {len(articles)}개 기사")

if __name__ == "__main__":
    main()
