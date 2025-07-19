import requests
import csv
import time
from bs4 import BeautifulSoup
from datetime import datetime
import re

class DaumNewsCollector:
    def __init__(self, api_key):
        """
        Daum News Collector 초기화
        
        Args:
            api_key (str): Kakao REST API 키
        """
        self.api_key = api_key
        self.base_url = "https://dapi.kakao.com/v2/search/web"
        self.headers = {
            "Authorization": f"KakaoAK {api_key}"
        }
    
    def search_news(self, query, pages=5, size=50):
        """
        뉴스 검색 함수
        
        Args:
            query (str): 검색어
            pages (int): 검색할 페이지 수
            size (int): 페이지당 결과 수 (최대 50)
        
        Returns:
            list: 뉴스 기사 정보 리스트
        """
        all_news = []
        
        # "뉴스" 키워드를 추가하여 뉴스 기사 위주로 검색
        search_query = f"{query} 뉴스"
        
        for page in range(1, pages + 1):
            params = {
                "query": search_query,
                "sort": "recency",  # 최신순 정렬
                "page": page,
                "size": size
            }
            
            try:
                response = requests.get(self.base_url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                documents = data.get('documents', [])
                
                # 뉴스 사이트 URL 필터링
                news_sites = [
                    'news.naver.com', 'news.daum.net', 'v.media.daum.net',
                    'news.jtbc.co.kr', 'news.sbs.co.kr', 'news.kbs.co.kr',
                    'news.mbc.co.kr', 'www.ytn.co.kr', 'news.mt.co.kr',
                    'www.sedaily.com', 'biz.chosun.com', 'www.mk.co.kr',
                    'www.hankyung.com', 'www.etnews.com', 'zdnet.co.kr'
                ]
                
                for doc in documents:
                    url = doc.get('url', '')
                    if any(site in url for site in news_sites):
                        all_news.append(doc)
                
                # API 호출 제한을 위한 딜레이
                time.sleep(0.1)
                
                # 마지막 페이지인지 확인
                if data.get('meta', {}).get('is_end', True):
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"API 요청 실패 (페이지 {page}): {e}")
                continue
        
        return all_news
    
    def extract_reporter_name(self, url):
        """
        뉴스 기사 URL에서 기자명 추출
        
        Args:
            url (str): 뉴스 기사 URL
        
        Returns:
            str: 기자명 (추출 실패시 "정보없음")
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 다양한 뉴스 사이트의 기자명 패턴
            reporter_patterns = [
                # 네이버 뉴스
                {'selector': '.media_end_head_journalist .name', 'attr': 'text'},
                {'selector': '.byline_s .name', 'attr': 'text'},
                
                # 다음 뉴스
                {'selector': '.info_reporter .name', 'attr': 'text'},
                {'selector': '.txt_info .name_txt', 'attr': 'text'},
                
                # 기타 패턴
                {'selector': '.reporter', 'attr': 'text'},
                {'selector': '.author', 'attr': 'text'},
                {'selector': '[class*="reporter"]', 'attr': 'text'},
                {'selector': '[class*="author"]', 'attr': 'text'},
            ]
            
            for pattern in reporter_patterns:
                element = soup.select_one(pattern['selector'])
                if element:
                    text = element.get_text(strip=True)
                    # "기자" 단어 제거 및 정리
                    text = re.sub(r'\s*기자\s*', '', text)
                    text = re.sub(r'\s*기자$', '', text)
                    if text and len(text) <= 10:  # 기자명은 일반적으로 10자 이내
                        return text
            
            # 본문에서 기자명 패턴 찾기
            content = soup.get_text()
            reporter_match = re.search(r'([가-힣]{2,4})\s*기자', content)
            if reporter_match:
                return reporter_match.group(1)
                
        except Exception as e:
            print(f"기자명 추출 실패 ({url}): {e}")
        
        return "정보없음"
    
    def clean_text(self, text):
        """
        텍스트 정리 (HTML 태그 제거, 특수문자 정리)
        
        Args:
            text (str): 원본 텍스트
        
        Returns:
            str: 정리된 텍스트
        """
        if not text:
            return ""
        
        # HTML 태그 제거
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text()
        
        # 불필요한 공백 정리
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def format_datetime(self, datetime_str):
        """
        날짜 형식 변환 (ISO 8601 -> YYYY-MM-DD HH:MM:SS)
        
        Args:
            datetime_str (str): ISO 8601 형식 날짜
        
        Returns:
            str: 포맷된 날짜
        """
        try:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return datetime_str
    
    def save_to_csv(self, news_list, filename="daum_news.csv"):
        """
        뉴스 데이터를 CSV 파일로 저장
        
        Args:
            news_list (list): 뉴스 데이터 리스트
            filename (str): 저장할 파일명
        """
        if not news_list:
            print("저장할 뉴스 데이터가 없습니다.")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['제목', '날짜', '기자명', '본문']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for i, news in enumerate(news_list, 1):
                print(f"처리 중... ({i}/{len(news_list)})")
                
                title = self.clean_text(news.get('title', ''))
                content = self.clean_text(news.get('contents', ''))
                datetime_formatted = self.format_datetime(news.get('datetime', ''))
                url = news.get('url', '')
                
                # 기자명 추출 (시간이 오래 걸릴 수 있음)
                reporter = self.extract_reporter_name(url)
                
                writer.writerow({
                    '제목': title,
                    '날짜': datetime_formatted,
                    '기자명': reporter,
                    '본문': content
                })
                
                # 요청 간격 조절 (서버 부하 방지)
                time.sleep(0.5)
        
        print(f"CSV 파일 저장 완료: {filename}")


def main():
    """
    메인 실행 함수
    """
    # Kakao REST API 키 설정
    API_KEY = "1e05240647e9dd57e0c5aa6666ce599c"  # 여기에 실제 API 키를 입력하세요
    
    if API_KEY == "YOUR_KAKAO_REST_API_KEY":
        print("API 키를 설정해주세요!")
        return
    
    # 뉴스 수집기 초기화
    collector = DaumNewsCollector(API_KEY)
    
    # 검색어 설정
    search_keyword = input("검색할 키워드를 입력하세요: ")
    if not search_keyword:
        search_keyword = "AI"  # 기본 검색어
    
    print(f"'{search_keyword}' 관련 뉴스를 검색합니다...")
    
    # 뉴스 검색 (최대 5페이지, 페이지당 50개)
    news_list = collector.search_news(search_keyword, pages=3, size=50)
    
    print(f"총 {len(news_list)}개의 뉴스를 찾았습니다.")
    
    if news_list:
        # CSV 파일로 저장
        filename = f"daum_news_{search_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        collector.save_to_csv(news_list, filename)
    else:
        print("검색 결과가 없습니다.")


if __name__ == "__main__":
    main()
