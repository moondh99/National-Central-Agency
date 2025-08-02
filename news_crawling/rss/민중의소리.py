import requests
import xml.etree.ElementTree as ET
import csv
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import json
from email.utils import parsedate_tz
import html

def parse_vop_rss_to_csv():
    """
    민중의소리 RSS 피드를 파싱하여 제목/날짜/기자명/본문 순으로 CSV 파일에 저장
    """
    
    # 민중의소리 RSS URL (HTTP 사용)
    rss_url = "http://www.vop.co.kr/rss"
    
    # CSV 파일명 (현재 날짜 기준)
    csv_filename = f"results/vop_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    try:
        # RSS 피드 가져오기
        print("민중의소리 RSS 피드를 가져오는 중...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        
        # XML 파싱
        root = ET.fromstring(response.content)
        
        # 기사 목록 추출
        items = root.findall('.//item')
        print(f"총 {len(items)}개의 기사를 발견했습니다.")
        
        if len(items) == 0:
            print("⚠️ RSS에서 기사를 찾을 수 없습니다. 최신 기사를 웹사이트에서 직접 가져오겠습니다.")
            return parse_vop_website_to_csv()
        
        # 세션 생성 (연결 재사용)
        session = requests.Session()
        session.headers.update(headers)
        session.verify = False
        
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
                    title = html.unescape(title)
                    
                    # 날짜 포맷 정리
                    formatted_date = format_date(pub_date)
                    
                    print(f"처리 중: {i}/{len(items)} - {title[:50]}...")
                    
                    # 개별 기사 페이지에서 상세 정보 추출
                    article_content, reporter, article_date = get_vop_article_details(session, link)
                    
                    # RSS 날짜가 없으면 기사에서 추출한 날짜 사용
                    final_date = formatted_date or article_date
                    
                    # CSV에 데이터 쓰기
                    writer.writerow([title, final_date, reporter, article_content])
                    
                    # 서버 부하 방지를 위한 지연
                    time.sleep(1.5)
                    
                except Exception as e:
                    print(f"기사 처리 중 오류 발생: {e}")
                    # 오류 발생시에도 기본 정보는 저장
                    writer.writerow([title, formatted_date, "정보없음", "본문 추출 실패"])
                    continue
        
        print(f"\n✅ CSV 파일이 생성되었습니다: {csv_filename}")
        print(f"📊 총 {len(items)}개 기사 처리 완료")
        return csv_filename
        
    except Exception as e:
        print(f"❌ RSS 파싱 중 오류 발생: {e}")
        print("🔄 웹사이트에서 직접 최신 기사를 가져오겠습니다...")
        return parse_vop_website_to_csv()

def parse_vop_website_to_csv():
    """
    민중의소리 웹사이트에서 직접 최신 기사를 가져와서 CSV로 저장
    """
    csv_filename = f"results/vop_news_web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        session.verify = False
        
        # 민중의소리 메인페이지에서 최신 기사 링크 추출
        print("민중의소리 웹사이트에서 최신 기사를 가져오는 중...")
        response = session.get("http://www.vop.co.kr/", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 기사 링크 찾기 (민중의소리 특화)
        article_links = []
        
        # 다양한 기사 링크 패턴 시도
        link_patterns = [
            'a[href*="/A000"]',  # 민중의소리 기사 ID 패턴
            '.article-list a',
            '.news-list a',
            '.main-news a',
            'a[href*="vop.co.kr/A"]'
        ]
        
        for pattern in link_patterns:
            links = soup.select(pattern)
            for link in links:
                href = link.get('href')
                if href and '/A000' in href:
                    if href.startswith('/'):
                        href = 'http://www.vop.co.kr' + href
                    elif not href.startswith('http'):
                        href = 'http://www.vop.co.kr/' + href
                    
                    if href not in article_links:
                        article_links.append(href)
            
            if article_links:
                break
        
        # 추가로 텍스트에서 기사 링크 찾기
        if not article_links:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link['href']
                if '/A000' in href:
                    if href.startswith('/'):
                        href = 'http://www.vop.co.kr' + href
                    elif not href.startswith('http'):
                        href = 'http://www.vop.co.kr/' + href
                    article_links.append(href)
        
        # 중복 제거 및 상위 20개만
        article_links = list(set(article_links))[:20]
        
        if not article_links:
            print("❌ 웹사이트에서 기사 링크를 찾을 수 없습니다.")
            return None
            
        print(f"총 {len(article_links)}개의 기사 링크를 발견했습니다.")
        
        # CSV 파일 생성
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            # 헤더 작성
            writer.writerow(['제목', '날짜', '기자명', '본문'])
            
            for i, link in enumerate(article_links, 1):
                try:
                    print(f"처리 중: {i}/{len(article_links)} - {link}")
                    
                    # 개별 기사 페이지에서 정보 추출
                    article_content, reporter, article_date, title = get_vop_article_details_full(session, link)
                    
                    # CSV에 데이터 쓰기
                    writer.writerow([title, article_date, reporter, article_content])
                    
                    # 서버 부하 방지를 위한 지연
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"기사 처리 중 오류 발생: {e}")
                    continue
        
        print(f"\n✅ CSV 파일이 생성되었습니다: {csv_filename}")
        return csv_filename
        
    except Exception as e:
        print(f"❌ 웹사이트 파싱 중 오류 발생: {e}")
        return None

def format_date(date_string):
    """
    날짜 문자열을 표준 형식으로 변환
    """
    if not date_string:
        return ""
    
    try:
        # RFC 2822 형식 파싱 시도
        parsed = parsedate_tz(date_string)
        if parsed:
            timestamp = time.mktime(parsed[:9])
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    
    # ISO 형식 시도
    try:
        date_string = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_string)
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    
    return date_string

def get_vop_article_details(session, url):
    """
    민중의소리 기사 URL에서 본문, 기자명, 날짜를 추출
    """
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 본문 추출 (민중의소리 특화)
        content = extract_vop_content(soup)
        
        # 기자명 추출 (민중의소리 특화)
        reporter = extract_vop_reporter(soup, content)
        
        # 기사 날짜 추출
        article_date = extract_vop_date(soup)
        
        # HTML 엔티티 디코딩
        content = html.unescape(content)
        reporter = html.unescape(reporter)
            
        return content, reporter, article_date
        
    except Exception as e:
        print(f"  ⚠️ 기사 상세 정보 추출 오류: {e}")
        return "본문 추출 실패", "정보없음", ""

def get_vop_article_details_full(session, url):
    """
    민중의소리 기사 URL에서 제목, 본문, 기자명, 날짜를 모두 추출
    """
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 제목 추출
        title = extract_vop_title(soup)
        
        # 본문 추출
        content = extract_vop_content(soup)
        
        # 기자명 추출
        reporter = extract_vop_reporter(soup, content)
        
        # 기사 날짜 추출
        article_date = extract_vop_date(soup)
        
        # HTML 엔티티 디코딩
        title = html.unescape(title)
        content = html.unescape(content)
        reporter = html.unescape(reporter)
            
        return content, reporter, article_date, title
        
    except Exception as e:
        print(f"  ⚠️ 기사 정보 추출 오류: {e}")
        return "본문 추출 실패", "정보없음", "", "제목 추출 실패"

def extract_vop_title(soup):
    """
    민중의소리 기사 제목 추출
    """
    # 제목 선택자들
    title_selectors = [
        'h1.title',
        'h1',
        '.article-title',
        '.news-title',
        'title'
    ]
    
    for selector in title_selectors:
        element = soup.select_one(selector)
        if element:
            title = element.get_text(strip=True)
            if title and len(title) > 5:
                # "민중의소리" 등 불필요한 텍스트 제거
                title = re.sub(r'\s*-\s*민중의소리.*$', '', title)
                return title
    
    return "제목 없음"

def extract_vop_content(soup):
    """
    민중의소리 기사 본문 추출
    """
    content = ""
    
    # 민중의소리 본문 선택자들
    content_selectors = [
        '.article-content',
        '.news-content', 
        '.content',
        '#article-content',
        '.article-body',
        'div[class*="content"]'
    ]
    
    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            content_parts = []
            for element in elements:
                # 광고나 관련기사 등 제거
                for unwanted in element.find_all(['script', 'style', 'aside', '.ad', '.related', '.recommend', '.banner']):
                    unwanted.decompose()
                
                # 텍스트 추출
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 50:
                    # 불필요한 내용 필터링
                    lines = text.split('\n')
                    filtered_lines = []
                    for line in lines:
                        line = line.strip()
                        if len(line) > 15 and not is_vop_unwanted_content(line):
                            filtered_lines.append(line)
                    
                    if filtered_lines:
                        content = ' '.join(filtered_lines)
                        break
            
            if content:
                break
    
    # 전체 본문에서 추출 (마지막 수단)
    if not content:
        # 특정 패턴으로 본문 찾기
        paragraphs = soup.find_all('p')
        content_parts = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 30 and not is_vop_unwanted_content(text):
                content_parts.append(text)
        
        if content_parts:
            content = ' '.join(content_parts[:10])  # 처음 10개 문단
    
    # 본문 정리 (너무 길면 자르기)
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    return content

def extract_vop_reporter(soup, content):
    """
    민중의소리 기자명 추출
    """
    reporter = "기자명 없음"
    
    # 1. CSS 선택자로 기자명 찾기
    reporter_selectors = [
        '.reporter',
        '.writer', 
        '.author',
        '.byline',
        '.journalist',
        '.article-info .reporter',
        '.article-info .writer',
        'span[class*="reporter"]',
        'span[class*="writer"]'
    ]
    
    for selector in reporter_selectors:
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text(strip=True)
            if text and ('기자' in text or '특파원' in text):
                return clean_vop_reporter_name(text)
    
    # 2. 본문에서 기자명 패턴 찾기
    if content:
        # 민중의소리 특화 패턴
        patterns = [
            r'([가-힣]{2,4})\s*(기자|특파원)\s*응원하기',  # "기자 응원하기" 패턴
            r'([가-힣]{2,4})\s*(기자|특파원)$',           # 줄 끝에 있는 경우
            r'([가-힣]{2,4})\s*(기자|특파원)\s*=',        # "기자=" 형태
            r'기자\s*([가-힣]{2,4})',                      # "기자 이름"
            r'([가-힣]{2,4})\s*([가-힣]{2,4})\s*(기자|특파원)',  # "성 이름 기자"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                match = matches[-1]  # 마지막 매치 사용
                if isinstance(match, tuple):
                    if len(match) >= 2:
                        name = match[0] if len(match[0]) >= 2 else match[0] + match[1]
                        title = match[-1]
                        return f"{name} {title}"
                break
    
    # 3. 페이지 하단에서 찾기
    footer_text = soup.get_text()
    footer_patterns = [
        r'([가-힣]{2,4})\s*(기자|특파원)\s*응원하기',
        r'([가-힣]{2,4})\s*(기자|특파원)\s*\w*@\w*'
    ]
    
    for pattern in footer_patterns:
        matches = re.findall(pattern, footer_text)
        if matches:
            match = matches[-1]
            if isinstance(match, tuple):
                name = match[0]
                title = match[1]
                return f"{name} {title}"
    
    return reporter

def extract_vop_date(soup):
    """
    민중의소리 기사 날짜 추출
    """
    # 날짜 선택자들
    date_selectors = [
        '.date',
        '.article-date',
        '.news-date',
        '.pub-date',
        '.published',
        '.article-info .date',
        'time'
    ]
    
    for selector in date_selectors:
        element = soup.select_one(selector)
        if element:
            date_text = element.get_text(strip=True)
            # 날짜 형식 정규화
            date_match = re.search(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})', date_text)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    # 본문에서 날짜 찾기
    text = soup.get_text()
    date_patterns = [
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
        r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})',
        r'(\d{4})/(\d{1,2})/(\d{1,2})'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        if matches:
            year, month, day = matches[0]
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return ""

def clean_vop_reporter_name(name):
    """
    민중의소리 기자명 정리
    """
    if not name:
        return "기자명 없음"
    
    # HTML 태그 제거
    name = re.sub(r'<[^>]+>', '', name)
    
    # 불필요한 문자 제거
    name = re.sub(r'[^\w\s가-힣·]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # "응원하기" 등 제거
    name = re.sub(r'\s*(응원하기|후원하기)\s*', '', name)
    
    # 이메일 주소 제거
    name = re.sub(r'\S+@\S+', '', name).strip()
    
    # "기자", "특파원" 등이 포함되어 있으면 그대로 반환
    if any(title in name for title in ['기자', '특파원', '논설위원', '편집위원']):
        return name
    
    # 이름만 있는 경우 " 기자" 추가
    if name and name != "기자명 없음" and len(name) >= 2:
        return name + " 기자"
    
    return "기자명 없음"

def is_vop_unwanted_content(text):
    """
    민중의소리 불필요한 내용 필터링
    """
    unwanted_patterns = [
        '구독하기', '좋아요', '댓글', '공유', '신고', '저작권',
        '관련기사', '이전기사', '다음기사', '추천기사', '인기기사',
        '광고', 'AD', '프리미엄', '구독', '로그인', '회원가입',
        '카카오톡', '페이스북', '트위터', '네이버', '구글',
        'ⓒ', '무단전재', '재배포금지', 'Copyright', '저작권자',
        '민중의소리를 응원해주세요', '후원회원이 되어주세요', '기자 응원하기',
        '정기후원', '기자후원', '독자님의 응원', '독자님의 후원금',
        '기사 잘 보셨나요', '독자님의 응원이', '후원회원',
        '프린트', '이메일', '스크랩', '글자크기', '폰트'
    ]
    
    return any(pattern in text for pattern in unwanted_patterns)

def print_vop_sample_data(csv_filename):
    """
    생성된 CSV 파일의 샘플 데이터 출력
    """
    try:
        with open(csv_filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        print("\n📋 생성된 데이터 샘플:")
        print("=" * 60)
        
        # 헤더 출력
        if rows:
            print(f"컬럼: {' | '.join(rows[0])}")
            print("-" * 60)
            
            # 처음 3개 데이터 샘플 출력
            for i in range(1, min(4, len(rows))):
                row = rows[i]
                print(f"기사 {i}:")
                print(f"  제목: {row[0][:50]}...")
                print(f"  날짜: {row[1]}")
                print(f"  기자: {row[2]}")
                print(f"  본문: {row[3][:100]}...")
                print()
                
    except Exception as e:
        print(f"샘플 데이터 출력 오류: {e}")

def main():
    """
    메인 실행 함수
    """
    print("📰 민중의소리 RSS/웹 뉴스 데이터 수집기")
    print("=" * 60)
    print("📰 기능: RSS 피드 또는 웹사이트 → 제목/날짜/기자명/본문 추출 → CSV 저장")
    print("⏱️ 예상 소요 시간: 약 2-4분")
    print("=" * 60)
    
    start_time = time.time()
    csv_file = parse_vop_rss_to_csv()
    end_time = time.time()
    
    if csv_file:
        print("=" * 60)
        print("✅ 데이터 수집이 성공적으로 완료되었습니다!")
        print(f"📁 저장된 파일: {csv_file}")
        print(f"⏱️ 총 소요 시간: {int(end_time - start_time)}초")
        
        # 샘플 데이터 출력
        print_vop_sample_data(csv_file)
        
        print("\n🔧 민중의소리 특화 기능:")
        print("  • RSS 피드 우선, 실패시 웹사이트 직접 크롤링")
        print("  • 민중의소리 기사 구조 최적화")
        print("  • '기자 응원하기' 패턴 인식")
        print("  • HTTP/HTTPS 자동 처리")
        print("  • SSL 인증서 문제 회피")
        
    else:
        print("❌ 데이터 수집 중 오류가 발생했습니다.")
        print("💡 인터넷 연결이나 웹사이트 접근성을 확인해주세요.")

if __name__ == "__main__":
    main()
