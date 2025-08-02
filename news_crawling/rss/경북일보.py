import feedparser
import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import random
from datetime import datetime
import logging

class KyongbukRSSCollector:
    def __init__(self):
        self.base_url = "https://www.kyongbuk.co.kr"
        self.rss_urls = {
            "전체기사": "https://www.kyongbuk.co.kr/rss/allArticle.xml",
            "인기기사": "https://www.kyongbuk.co.kr/rss/clickTop.xml",
            "경북대구": "https://www.kyongbuk.co.kr/rss/S1N1.xml",
            "지방의회": "https://www.kyongbuk.co.kr/rss/S1N2.xml",
            "정치": "https://www.kyongbuk.co.kr/rss/S1N3.xml",
            "경제": "https://www.kyongbuk.co.kr/rss/S1N4.xml",
            "사회": "https://www.kyongbuk.co.kr/rss/S1N5.xml",
            "문화라이프": "https://www.kyongbuk.co.kr/rss/S1N6.xml",
            "사람들": "https://www.kyongbuk.co.kr/rss/S1N9.xml",
            "뉴콘텐츠": "https://www.kyongbuk.co.kr/rss/S1N11.xml",
            "미디어": "https://www.kyongbuk.co.kr/rss/S1N12.xml",
            "헬스": "https://www.kyongbuk.co.kr/rss/S1N23.xml",
            "경북일보TV": "https://www.kyongbuk.co.kr/rss/S2N87.xml"
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
                logging.FileHandler('kyongbuk_rss.log', encoding='utf-8'),
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
            
            # 기자 정보 먼저 추출 (경북일보의 구조: "기자명 이봉한 기자")
            reporter = ""
            reporter_elem = soup.find(string=re.compile(r'기자명'))
            if reporter_elem:
                # 기자명 다음에 오는 텍스트에서 기자명 추출
                next_text = reporter_elem.parent.get_text() if reporter_elem.parent else ""
                reporter_match = re.search(r'기자명\s+([가-힣]{2,4})\s*기자', next_text)
                if reporter_match:
                    reporter = reporter_match.group(1)
            
            # 기사 본문 추출 - 경북일보의 특별한 구조 고려
            content = ""
            
            # 전체 페이지에서 본문만 추출하기 위해 특정 패턴 사용
            page_text = soup.get_text()
            
            # 기사 시작점과 끝점 찾기
            # 시작점: 이미지 캡션 이후부터 (보통 "경북소방본부", "사진=" 등의 캡션 다음)
            # 끝점: "저작권자" 이전까지
            
            # 여러 가능한 시작 패턴들
            start_patterns = [
                r'경북소방본부\s*',
                r'사진=.*?\s*', 
                r'제공.*?\s*',
                r'승인\s+\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}.*?댓글\s+\d+\s*',
            ]
            
            start_pos = 0
            for pattern in start_patterns:
                match = re.search(pattern, page_text)
                if match:
                    start_pos = match.end()
                    break
            
            # 끝점 찾기
            end_patterns = [
                r'저작권자.*?무단전재.*?재배포.*?금지',
                r'개의\s*댓글',
                r'댓글\s*정렬'
            ]
            
            end_pos = len(page_text)
            for pattern in end_patterns:
                match = re.search(pattern, page_text)
                if match:
                    end_pos = match.start()
                    break
            
            # 본문 텍스트 추출
            if start_pos < end_pos:
                content = page_text[start_pos:end_pos].strip()
            else:
                # 패턴 매칭이 실패한 경우 전체 텍스트에서 추출
                content = page_text
            
            # 텍스트 정제
            content = re.sub(r'\s+', ' ', content)  # 연속된 공백 정리
            content = re.sub(r'\n+', '\n', content)  # 연속된 줄바꿈 정리
            
            # 불필요한 텍스트 제거
            unwanted_patterns = [
                r'기자명\s+[가-힣]{2,4}\s*기자',
                r'승인\s+\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}',
                r'지면게재일\s+\d{4}년\s+\d{2}월\s+\d{2}일\s+[가-힣]+요일',
                r'댓글\s+\d+',
                r'저작권자.*?무단전재.*?재배포.*?금지',
                r'개의\s*댓글',
                r'댓글\s*정렬',
                r'BEST댓글.*?자동으로\s*노출됩니다\.',
                r'댓글삭제.*?삭제하시겠습니까\?',
                r'댓글수정.*?가능합니다\.',
                r'홈경북대구경북구미사회사건사고',
                r'^\s*경북일보\s*$',
                r'^\s*구미.*?추돌.*?중태\s*$'  # 제목 중복 제거
            ]
            
            for pattern in unwanted_patterns:
                content = re.sub(pattern, '', content, flags=re.MULTILINE | re.IGNORECASE)
            
            # 최종 정제
            content = re.sub(r'\s+', ' ', content).strip()
            
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
            filename = f'results/kyongbuk_articles_{timestamp}.csv'
        
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
    collector = KyongbukRSSCollector()
    
    print("=== 경북일보 RSS 수집기 (개선된 버전) ===")
    print("1. 전체기사 수집")
    print("2. 인기기사 수집") 
    print("3. 경북대구 수집")
    print("4. 지방의회 수집")
    print("5. 정치 수집")
    print("6. 경제 수집")
    print("7. 사회 수집")
    print("8. 문화라이프 수집")
    print("9. 사람들 수집")
    print("10. 뉴콘텐츠 수집")
    print("11. 미디어 수집")
    print("12. 헬스 수집")
    print("13. 경북일보TV 수집")
    print("14. 모든 카테고리 수집")
    
    choice = input("선택하세요 (1-14): ").strip()
    
    categories = {
        "1": "전체기사",
        "2": "인기기사",
        "3": "경북대구",
        "4": "지방의회",
        "5": "정치",
        "6": "경제",
        "7": "사회",
        "8": "문화라이프",
        "9": "사람들",
        "10": "뉴콘텐츠",
        "11": "미디어",
        "12": "헬스",
        "13": "경북일보TV"
    }
    
    if choice in categories:
        articles = collector.collect_rss_data(categories[choice], 50)
        collector.save_to_csv(articles)
    elif choice == "14":
        articles = collector.collect_all_categories(30)
        collector.save_to_csv(articles)
    else:
        print("잘못된 선택입니다.")
        return
    
    print(f"수집 완료: 총 {len(articles)}개 기사")

if __name__ == "__main__":
    main()
