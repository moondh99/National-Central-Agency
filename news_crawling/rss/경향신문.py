import requests
import xml.etree.ElementTree as ET
import csv
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import json

def parse_khan_rss_to_csv():
    """
    경향신문 RSS 피드를 파싱하여 제목/날짜/기자명/본문 순으로 CSV 파일에 저장 (개선된 버전)
    """
    
    # 경향신문 RSS URL
    rss_url = "https://www.khan.co.kr/rss/rssdata/total_news.xml"
    
    # CSV 파일명 (현재 날짜 기준)
    csv_filename = f"results/khan_news_improved_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    try:
        # RSS 피드 가져오기
        print("RSS 피드를 가져오는 중...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # XML 파싱
        root = ET.fromstring(response.content)
        
        # 기사 목록 추출
        items = root.findall('.//item')
        print(f"총 {len(items)}개의 기사를 발견했습니다.")
        
        # CSV 파일 생성
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            # 헤더 작성
            writer.writerow(['제목', '날짜', '기자명', '본문'])
            
            for i, item in enumerate(items, 1):
                try:
                    # RSS에서 기본 정보 추출
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    
                    # CDATA 태그 제거
                    title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                    
                    # 날짜 포맷 정리
                    formatted_date = format_date(pub_date)
                    
                    print(f"처리 중: {i}/{len(items)} - {title[:50]}...")
                    
                    # 개별 기사 페이지에서 상세 정보 추출
                    article_content, reporter = get_article_details_improved(link)
                    
                    # CSV에 데이터 쓰기
                    writer.writerow([title, formatted_date, reporter, article_content])
                    
                    # 서버 부하 방지를 위한 지연
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"기사 처리 중 오류 발생: {e}")
                    # 오류 발생시에도 기본 정보는 저장
                    writer.writerow([title, formatted_date, "정보없음", "본문 추출 실패"])
                    continue
        
        print(f"CSV 파일이 생성되었습니다: {csv_filename}")
        return csv_filename
        
    except Exception as e:
        print(f"RSS 파싱 중 오류 발생: {e}")
        return None

def format_date(date_string):
    """
    날짜 문자열을 표준 형식으로 변환
    """
    if not date_string:
        return ""
    
    try:
        # RFC 2822 형식 파싱 시도
        from email.utils import parsedate_tz
        import time
        
        parsed = parsedate_tz(date_string)
        if parsed:
            timestamp = time.mktime(parsed[:9])
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    
    return date_string

def get_article_details_improved(url):
    """
    개별 기사 URL에서 본문과 기자명을 추출 (개선된 버전)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 본문 추출 (다양한 선택자 시도)
        content = ""
        
        # 경향신문의 다양한 기사 본문 선택자들
        content_selectors = [
            'div.art-body',
            'div#article-body', 
            'div.article-body',
            'div.news-body',
            'div.view-body',
            '.art-body p',
            'article .content',
            'div[data-article-body]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content_parts = []
                for element in elements:
                    # 광고나 관련기사 등 제거
                    for unwanted in element.find_all(['script', 'style', 'aside', '.ad', '.related', '.recommend']):
                        unwanted.decompose()
                    
                    # 텍스트 추출
                    paragraphs = element.find_all(['p', 'div'], recursive=True)
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 15 and not is_unwanted_content(text):
                            content_parts.append(text)
                
                if content_parts:
                    content = " ".join(content_parts)
                    break
        
        # 전체 텍스트에서 본문 추출 (마지막 수단)
        if not content:
            all_text = soup.get_text()
            paragraphs = all_text.split('\n')
            content_parts = []
            for para in paragraphs:
                para = para.strip()
                if len(para) > 30 and not is_unwanted_content(para):
                    content_parts.append(para)
            content = " ".join(content_parts[:10])  # 처음 10개 문단만
        
        # 기자명 추출 (다양한 방법 시도)
        reporter = extract_reporter_name(soup, content)
        
        # 본문 정리 (너무 길면 자르기)
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        # HTML 엔티티 디코딩
        import html
        content = html.unescape(content)
        reporter = html.unescape(reporter)
            
        return content, reporter
        
    except Exception as e:
        print(f"기사 상세 정보 추출 오류 ({url}): {e}")
        return "본문 추출 실패", "정보없음"

def extract_reporter_name(soup, content):
    """
    기자명 추출을 위한 다양한 방법 시도
    """
    reporter = "기자명 없음"
    
    # 1. 클래스명으로 기자명 찾기
    reporter_selectors = [
        '.writer', '.reporter', '.author', '.byline',
        '.art-writer', '.news-writer', '.article-writer',
        '[class*="writer"]', '[class*="reporter"]', '[class*="author"]'
    ]
    
    for selector in reporter_selectors:
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text(strip=True)
            if text and ('기자' in text or '특파원' in text or '논설위원' in text):
                reporter = clean_reporter_name(text)
                return reporter
    
    # 2. 메타데이터에서 찾기
    meta_author = soup.find('meta', {'name': 'author'})
    if meta_author and meta_author.get('content'):
        reporter = clean_reporter_name(meta_author['content'])
        return reporter
    
    # 3. JSON-LD 구조화 데이터에서 찾기
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and 'author' in data:
                author = data['author']
                if isinstance(author, dict) and 'name' in author:
                    reporter = clean_reporter_name(author['name'])
                    return reporter
                elif isinstance(author, str):
                    reporter = clean_reporter_name(author)
                    return reporter
        except:
            continue
    
    # 4. 본문에서 기자명 패턴 찾기
    if content:
        # "이름 기자", "이름 특파원" 등의 패턴
        patterns = [
            r'([가-힣]{2,4})\s*(기자|특파원|논설위원|편집위원)',
            r'기자\s*([가-힣]{2,4})',
            r'([가-힣]{2,4})\s*=',  # "기자명=" 형태
            r'글\s*([가-힣]{2,4})',  # "글 기자명" 형태
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                if isinstance(matches[0], tuple):
                    reporter = matches[0][0] + " 기자"
                else:
                    reporter = matches[0] + " 기자"
                return reporter
    
    # 5. 기사 끝부분에서 이메일과 함께 있는 기자명 찾기
    email_pattern = r'([가-힣]{2,4})\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_matches = re.findall(email_pattern, str(soup))
    if email_matches:
        reporter = email_matches[0] + " 기자"
        return reporter
    
    return reporter

def clean_reporter_name(name):
    """
    기자명 정리
    """
    if not name:
        return "기자명 없음"
    
    # 불필요한 텍스트 제거
    name = re.sub(r'[^\w\s가-힣]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # 기자, 특파원 등이 포함되어 있으면 그대로 반환
    if any(title in name for title in ['기자', '특파원', '논설위원', '편집위원']):
        return name
    
    # 그렇지 않으면 " 기자" 추가
    if name and name != "기자명 없음":
        return name + " 기자"
    
    return "기자명 없음"

def is_unwanted_content(text):
    """
    불필요한 내용 필터링
    """
    unwanted_patterns = [
        '구독하기', '좋아요', '댓글', '공유', '신고', '저작권',
        '관련기사', '이전기사', '다음기사', '추천기사', '인기기사',
        '광고', 'AD', '프리미엄', '구독', '로그인', '회원가입',
        '카카오톡', '페이스북', '트위터', '네이버', '구글',
        'ⓒ', '무단전재', '재배포금지', 'Copyright'
    ]
    
    return any(pattern in text for pattern in unwanted_patterns)

def main():
    """
    메인 실행 함수
    """
    print("경향신문 RSS 뉴스 데이터 수집을 시작합니다... (개선된 버전)")
    print("=" * 60)
    
    csv_file = parse_khan_rss_to_csv()
    
    if csv_file:
        print("=" * 60)
        print("데이터 수집이 완료되었습니다!")
        print(f"저장된 파일: {csv_file}")
        print("\n주요 개선사항:")
        print("1. 향상된 기자명 추출 알고리즘")
        print("2. 개선된 본문 추출 방식")
        print("3. 날짜 형식 표준화")
        print("4. 더 강력한 오류 처리")
        print("5. 불필요한 내용 필터링")
    else:
        print("데이터 수집 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main()
