import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging

class ImaeilRSSCollector:
    def __init__(self):
        self.base_url = "https://www.imaeil.com"
        self.rss_urls = {
            "최신기사": "https://www.imaeil.com/rss",
            "오피니언": "https://www.imaeil.com/rss?cate=opinion",
            "정치": "https://www.imaeil.com/rss?cate=politics",
            "경제": "https://www.imaeil.com/rss?cate=economy",
            "사회": "https://www.imaeil.com/rss?cate=society",
            "국제": "https://www.imaeil.com/rss?cate=nations",
            "문화": "https://www.imaeil.com/rss?cate=culture",
            "스포츠": "https://www.imaeil.com/rss?cate=sports",
            "연예": "https://www.imaeil.com/rss?cate=entertainment",
            "라이프": "https://www.imaeil.com/rss?cate=life"
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
                logging.FileHandler('imaeil_rss.log', encoding='utf-8'),
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
            
            # 매일신문의 기사 본문 추출
            content = ""
            
            # 전체 페이지 텍스트 가져오기
            page_text = soup.get_text()
            
            # 기자 정보 추출
            reporter = ""
            reporter_patterns = [
                r'([가-힣]{2,4})\s*기자\s+[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                r'([가-힣]{2,4})\s*기자',
                r'기자\s+([가-힣]{2,4})',
                r'([가-힣]{2,4})\s*특파원'
            ]
            
            for pattern in reporter_patterns:
                matches = re.findall(pattern, page_text)
                if matches:
                    reporter = matches[-1]  # 마지막 매치를 기자로 인식 (기사 끝부분)
                    break
            
            # 본문 추출 - 이미지 캡션 이후부터 기자 정보 이전까지
            lines = page_text.split('\n')
            content_lines = []
            start_collecting = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 이미지 캡션 이후부터 수집 시작
                if not start_collecting:
                    # 이미지 캡션이나 실제 기사 시작을 나타내는 패턴들
                    if (re.search(r'한미\s+정상회담을\s+앞두고', line) or
                        re.search(r'[가-힣]+\s+(대통령|시장|지사|의원)', line) or 
                        len(line) > 30):  # 충분한 길이의 문장
                        start_collecting = True
                        content_lines.append(line)
                else:
                    # 기자 정보나 저작권 정보 나오면 중단
                    if (re.search(r'([가-힣]{2,4})\s*기자', line) or
                        re.search(r'저작권자.*?매일신문', line) or
                        re.search(r'무단전재.*?재배포.*?금지', line)):
                        break
                    content_lines.append(line)
            
            content = ' '.join(content_lines)
            
            # 텍스트 정제
            content = re.sub(r'\s+', ' ', content)  # 연속된 공백 정리
            
            # 불필요한 텍스트 제거
            unwanted_patterns = [
                r'매일신문.*?뉴스',
                r'/연합뉴스',
                r'저작권자.*?매일신문.*?무단전재.*?재배포.*?금지',
                r'Copyright.*?매일신문.*?All.*?rights?.*?reserved',
                r'^\s*매일신문\s*$'
            ]
            
            for pattern in unwanted_patterns:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE)
            
            content = content.strip()
            
            return content, reporter
            
        except Exception as e:
            self.logger.error(f"기사 내용 추출 실패 - {article_url}: {str(e)}")
            return "", ""

    def collect_rss_data(self, category="최신기사", max_articles=50):
        """RSS 데이터 수집"""
        rss_url = self.rss_urls.get(category, self.rss_urls["최신기사"])
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
                    
                    # RSS에서 기자명 추출 (매일신문은 RSS에 author 정보 포함)
                    rss_reporter = ""
                    if hasattr(entry, 'author') and entry.author:
                        # "장성혁 기자 jsh0529@imaeil.com" 형태에서 기자명만 추출
                        author_match = re.search(r'([가-힣]{2,4})\s*기자', entry.author)
                        if author_match:
                            rss_reporter = author_match.group(1)
                    
                    # 발행일 처리
                    pub_date = ""
                    if hasattr(entry, 'published'):
                        try:
                            pub_date = entry.published
                        except:
                            pub_date = ""
                    
                    # 기사 본문 및 추가 기자 정보 추출
                    content, content_reporter = self.extract_article_content(link)
                    
                    # 기자명 결정 (RSS 우선, 본문 보조)
                    reporter = rss_reporter if rss_reporter else content_reporter
                    
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
            filename = f'results/imaeil_articles_{timestamp}.csv'
        
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
    collector = ImaeilRSSCollector()
    
    print("=== 매일신문 RSS 수집기 ===")
    print("1. 최신기사 수집")
    print("2. 오피니언 수집")
    print("3. 정치 수집")
    print("4. 경제 수집")
    print("5. 사회 수집")
    print("6. 국제 수집")
    print("7. 문화 수집")
    print("8. 스포츠 수집")
    print("9. 연예 수집")
    print("10. 라이프 수집")
    print("11. 모든 카테고리 수집")
    
    choice = input("선택하세요 (1-11): ").strip()
    
    categories = {
        "1": "최신기사",
        "2": "오피니언",
        "3": "정치",
        "4": "경제",
        "5": "사회",
        "6": "국제",
        "7": "문화",
        "8": "스포츠",
        "9": "연예",
        "10": "라이프"
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
