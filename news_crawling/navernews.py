import requests
import csv
import json
import urllib.parse
from datetime import datetime
import re
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse

class NaverNewsCollector:
    def __init__(self, client_id, client_secret):
        """
        네이버 뉴스 수집기 초기화
        
        Args:
            client_id (str): 네이버 개발자센터에서 발급받은 클라이언트 ID
            client_secret (str): 네이버 개발자센터에서 발급받은 클라이언트 시크릿
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        
    def search_news(self, query, display=100, start=1, sort="date"):
        """
        네이버 뉴스 검색
        
        Args:
            query (str): 검색어
            display (int): 검색 결과 개수 (최대 100)
            start (int): 검색 시작 위치
            sort (str): 정렬 방법 ('sim': 정확도순, 'date': 날짜순)
            
        Returns:
            dict: API 응답 데이터
        """
        headers = {
            'X-Naver-Client-Id': self.client_id,
            'X-Naver-Client-Secret': self.client_secret
        }
        
        params = {
            'query': query,
            'display': display,
            'start': start,
            'sort': sort
        }
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 요청 중 오류 발생: {e}")
            return None
    
    def extract_full_article_content(self, url):
        """
        뉴스 원문 URL에서 전체 기사 내용과 기자명 추출
        
        Args:
            url (str): 뉴스 원문 URL
            
        Returns:
            tuple: (전체 기사 내용, 기자명)
        """
        try:
            # 요청 간격 조절 (서버 부하 방지)
            time.sleep(1)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 기사 내용 추출
            article_content = self._extract_article_content_by_site(soup, url)
            
            # 기자명 추출
            reporter = self._extract_reporter_name(soup, article_content)
            
            return article_content, reporter
            
        except Exception as e:
            print(f"기사 내용 추출 중 오류 발생 ({url}): {e}")
            return "내용 추출 실패", "정보없음"
    
    def _extract_article_content_by_site(self, soup, url):
        """
        사이트별 기사 내용 추출 로직
        """
        domain = urlparse(url).netloc.lower()
        
        # 각 언론사별 기사 본문 selector 패턴
        content_selectors = {
            'yna.co.kr': ['.article-view__article-body', '.story-news-body', '.news-content'],
            'newsis.com': ['.viewer_body', '.article_text', '.content'],
            'yonhapnews.co.kr': ['.article-view__article-body', '.story-news-body'],
            'news1.kr': ['.article-body', '.news-content'],
            'newspim.com': ['.news_content', '.article_body'],
            'edaily.co.kr': ['.news_body', '.article_body'],
            'mk.co.kr': ['.art_txt', '.news_cnt_detail_wrap'],
            'hankyung.com': ['.txt_article', '.news_view'],
            'mt.co.kr': ['.textBody', '.article_content'],
            'etnews.com': ['.article_txt', '.news_body'],
            'dt.co.kr': ['.news_body_area', '.article_view'],
            'inews24.com': ['.articleView', '.news_textArea'],
        }
        
        # 도메인별 특화 selector 시도
        for domain_key, selectors in content_selectors.items():
            if domain_key in domain:
                for selector in selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        return self._clean_article_text(content_elem.get_text())
        
        # 일반적인 selector 패턴 시도
        general_selectors = [
            '.article-view__article-body',
            '.news_end',
            '.article_body',
            '.news_body',
            '.article_txt',
            '.textBody',
            '.articleView',
            '.news_content',
            '.content',
            '.txt_article',
            'div[itemprop="articleBody"]',
            'article',
            '.article-content',
            '#articleText',
            '#newsEndContents',
            '#CmAdContent',
        ]
        
        for selector in general_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                text = self._clean_article_text(content_elem.get_text())
                if len(text) > 100:  # 충분한 길이의 텍스트만 선택
                    return text
        
        # 최후의 수단: p 태그들에서 텍스트 추출
        paragraphs = soup.find_all('p')
        if paragraphs:
            content_parts = []
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 20:  # 의미있는 길이의 텍스트만
                    content_parts.append(text)
            
            if content_parts:
                return '\n'.join(content_parts)
        
        return "기사 내용을 추출할 수 없습니다."
    
    def _extract_reporter_name(self, soup, article_text):
        """
        기자명 추출
        """
        # 기자명 패턴들
        reporter_patterns = [
            r'([가-힣]{2,4})\s*기자',
            r'기자\s*([가-힣]{2,4})',
            r'([가-힣]{2,4})\s*특파원',
            r'특파원\s*([가-힣]{2,4})',
            r'([가-힣]{2,4})\s*기자.*?@',
            r'기자\s*=\s*([가-힣]{2,4})',
            r'취재.*?([가-힣]{2,4})\s*기자',
            r'([가-힣]{2,4})\s*수습기자',
            r'([가-힣]{2,4})\s*연구위원',
        ]
        
        # 기사 텍스트에서 기자명 검색
        for pattern in reporter_patterns:
            matches = re.findall(pattern, article_text)
            if matches:
                # 가장 일반적인 이름 반환 (한글 2-4자)
                for match in matches:
                    if len(match) >= 2 and match.isalpha():
                        return match.strip()
        
        # 메타 태그에서 기자명 검색
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author and meta_author.get('content'):
            author = meta_author.get('content')
            if re.search(r'[가-힣]{2,4}', author):
                return author.strip()
        
        # byline 관련 태그에서 검색
        byline_selectors = ['.byline', '.reporter', '.author', '.writer']
        for selector in byline_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                for pattern in reporter_patterns:
                    match = re.search(pattern, text)
                    if match:
                        return match.group(1).strip()
        
        return "정보없음"
    
    def _clean_article_text(self, text):
        """
        기사 텍스트 정리
        """
        # 불필요한 문자열 제거
        unnecessary_patterns = [
            r'Copyright.*?All rights reserved',
            r'저작권.*?무단.*?금지',
            r'▶.*?바로가기',
            r'☞.*?클릭',
            r'\[.*?편집자.*?\]',
            r'※.*?문의.*?:',
            r'■.*?관련기사',
            r'◆.*?관련뉴스',
            r'▲.*?사진',
            r'<.*?>',  # HTML 태그
            r'\s+',   # 연속된 공백
        ]
        
        for pattern in unnecessary_patterns:
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
        
        # 문장 정리
        sentences = []
        for sentence in text.split('.'):
            sentence = sentence.strip()
            if len(sentence) > 10:  # 의미있는 길이의 문장만
                sentences.append(sentence)
        
        return '. '.join(sentences).strip()
    
    def clean_text(self, text):
        """
        HTML 태그 제거 및 텍스트 정리 (기존 메서드)
        """
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def format_date(self, date_str):
        """
        날짜 형식 변환
        """
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return date_str
    
    def collect_news_to_csv(self, query, filename=None, max_results=100, extract_full_content=True):
        """
        뉴스 검색 결과를 CSV 파일로 저장
        
        Args:
            query (str): 검색어
            filename (str): 저장할 파일명
            max_results (int): 최대 수집 뉴스 개수
            extract_full_content (bool): 전체 기사 내용 추출 여부
        """
        if filename is None:
            today = datetime.now().strftime("%Y%m%d")
            filename = f"{query}_뉴스_전체내용_{today}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['제목', '날짜', '기자명', '본문', '원문링크']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collected_count = 0
            start_position = 1
            
            print(f"'{query}' 검색 결과 수집 시작...")
            print(f"전체 기사 내용 추출: {'예' if extract_full_content else '아니오'}")
            
            while collected_count < max_results:
                display_count = min(100, max_results - collected_count)
                
                result = self.search_news(query, display=display_count, start=start_position)
                
                if not result or 'items' not in result:
                    print("더 이상 검색 결과가 없습니다.")
                    break
                
                items = result['items']
                if not items:
                    print("검색 결과가 없습니다.")
                    break
                
                print(f"현재 진행: {start_position}~{start_position + len(items) - 1}")
                
                for idx, item in enumerate(items):
                    print(f"  [{collected_count + 1}/{max_results}] 처리 중...")
                    
                    # 기본 정보 추출
                    title = self.clean_text(item.get('title', ''))
                    date = self.format_date(item.get('pubDate', ''))
                    original_link = item.get('originallink', '')
                    
                    if extract_full_content and original_link:
                        # 전체 기사 내용과 기자명 추출
                        full_content, reporter = self.extract_full_article_content(original_link)
                        content = full_content
                    else:
                        # API에서 제공하는 요약 내용 사용
                        content = self.clean_text(item.get('description', ''))
                        reporter = "정보없음"
                    
                    # CSV에 데이터 쓰기
                    writer.writerow({
                        '제목': title,
                        '날짜': date,
                        '기자명': reporter,
                        '본문': content,
                        '원문링크': original_link
                    })
                    
                    collected_count += 1
                    print(f"    완료: {title[:50]}...")
                    
                    if collected_count >= max_results:
                        break
                
                start_position += len(items)
                time.sleep(0.1)
        
        print(f"\n수집 완료! 총 {collected_count}건의 뉴스가 '{filename}' 파일에 저장되었습니다.")

# 사용 예제
def main():
    # 네이버 개발자센터에서 발급받은 인증 정보 입력
    CLIENT_ID = "P8CigFc2ZTd0V4vHgUf7"
    CLIENT_SECRET = "SZG2BX13Vy"
    
    # 뉴스 수집기 초기화
    collector = NaverNewsCollector(CLIENT_ID, CLIENT_SECRET)
    
    # 전체 기사 내용을 포함한 뉴스 수집
    search_keyword = "정책"
    
    collector.collect_news_to_csv(
        query=search_keyword,
        max_results=50,  # 수집할 뉴스 개수
        extract_full_content=True,  # 전체 기사 내용 추출
        filename=f"{search_keyword}_뉴스_전체내용_{datetime.now().strftime('%Y%m%d')}.csv"
    )

if __name__ == "__main__":
    main()
