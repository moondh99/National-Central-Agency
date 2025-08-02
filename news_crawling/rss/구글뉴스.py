import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random
from urllib.parse import urlparse, parse_qs

def get_random_user_agent():
    """랜덤 User-Agent 반환"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    return random.choice(user_agents)

def extract_google_news_content(url, rss_summary=""):
    """구글뉴스에서 실제 기사 URL 추출 및 본문 수집"""
    try:
        # 구글뉴스 URL에서 실제 기사 URL 추출
        actual_url = extract_actual_url_from_google_news(url)
        if not actual_url:
            print(f"    ⚠ 실제 기사 URL 추출 실패")
            return "", rss_summary if rss_summary else "URL 추출 실패"
        
        print(f"    실제 URL: {actual_url[:80]}...")
        
        session = requests.Session()
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache'
        }
        
        try:
            response = session.get(actual_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if len(response.content) < 1000:  # 1KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")
                
        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        full_text = soup.get_text()
        
        # 언론사별 기자명 추출 패턴
        reporter = extract_reporter_from_content(full_text, actual_url)
        
        # 본문 추출 - 다양한 언론사 구조에 대응
        content = extract_article_content(soup, actual_url)
        
        # 본문 정제
        content = clean_news_content(content, actual_url)
        
        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")
        
        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content
        
    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"

def extract_actual_url_from_google_news(google_news_url):
    """구글뉴스 URL에서 실제 기사 URL 추출"""
    try:
        # 구글뉴스 URL 패턴 분석
        if 'news.google.co.kr' in google_news_url:
            # URL 파라미터에서 실제 URL 추출 시도
            parsed_url = urlparse(google_news_url)
            params = parse_qs(parsed_url.query)
            
            # url 파라미터에서 추출
            if 'url' in params:
                return params['url'][0]
            
            # 구글 리다이렉트 서비스를 통한 추출
            session = requests.Session()
            headers = {'User-Agent': get_random_user_agent()}
            
            try:
                response = session.get(google_news_url, headers=headers, timeout=5, allow_redirects=True)
                return response.url
            except:
                pass
        
        # 이미 실제 URL인 경우
        return google_news_url
        
    except Exception as e:
        print(f"    URL 추출 오류: {e}")
        return google_news_url

def extract_reporter_from_content(full_text, url):
    """언론사별 기자명 추출"""
    reporter = ""
    
    # 언론사별 도메인 확인
    domain = urlparse(url).netloc.lower()
    
    # 기본 기자명 패턴들
    reporter_patterns = [
        r'([가-힣]{2,4})\s*기자\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+)',  # 기자명 기자 이메일
        r'([가-힣]{2,4})\s*기자',                                        # 기자명 기자
        r'기자\s*([가-힣]{2,4})',                                        # 기자 기자명
        r'([가-힣]{2,4})\s*특파원',                                      # 기자명 특파원
        r'([가-힣]{2,4})\s*편집위원',                                    # 기자명 편집위원
        r'([가-힣]{2,4})\s*팀장',                                        # 기자명 팀장
        r'([가-힣]{2,4})\s*기자\s*=',                                    # 기자명 기자 =
        r'취재\s*([가-힣]{2,4})',                                        # 취재 기자명
        r'글\s*([가-힣]{2,4})',                                          # 글 기자명
    ]
    
    # 기사 본문 끝 부분에서 기자명 찾기
    article_end = full_text[-1500:]  # 마지막 1500자에서 찾기
    
    for pattern in reporter_patterns:
        match = re.search(pattern, article_end)
        if match:
            reporter = match.group(1)
            reporter = re.sub(r'기자|특파원|편집위원|팀장|취재|글', '', reporter).strip()
            if len(reporter) >= 2 and len(reporter) <= 4:
                break
    
    return reporter

def extract_article_content(soup, url):
    """다양한 언론사의 기사 본문 추출"""
    content = ""
    domain = urlparse(url).netloc.lower()
    
    # 언론사별 맞춤 셀렉터
    content_selectors = []
    
    if 'chosun.com' in domain:
        content_selectors = ['div.article-body', 'div[class*="article"]']
    elif 'donga.com' in domain:
        content_selectors = ['div.article_txt', 'div[class*="article"]']
    elif 'joongang.co.kr' in domain:
        content_selectors = ['div.article_body', 'div[class*="article"]']
    elif 'hankyung.com' in domain:
        content_selectors = ['div.article-body', 'div.wrap_cont']
    elif 'mk.co.kr' in domain:
        content_selectors = ['div.article_content', 'div[class*="article"]']
    elif 'seoul.co.kr' in domain:
        content_selectors = ['div.article', 'div[class*="content"]']
    elif 'hani.co.kr' in domain:
        content_selectors = ['div.article-text', 'div[class*="article"]']
    elif 'khan.co.kr' in domain:
        content_selectors = ['div.art_body', 'div[class*="article"]']
    elif 'yna.co.kr' in domain:
        content_selectors = ['div.article', 'div[class*="content"]']
    
    # 공통 셀렉터 추가
    content_selectors.extend([
        'div[class*="article"]',
        'div[class*="content"]',
        'div[class*="news"]',
        'div[class*="text"]',
        'article',
        'main',
        'div[id*="article"]',
        'div.story-body',
        'div.entry-content'
    ])
    
    # 셀렉터로 본문 찾기
    for selector in content_selectors:
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text().strip()
            if len(text) > len(content):
                content = text
    
    # P 태그 기반 추출 (백업 방법)
    if len(content) < 200:
        paragraphs = soup.find_all('p')
        content_parts = []
        
        for p in paragraphs:
            text = p.get_text().strip()
            if (len(text) > 20 and 
                not re.search(r'입력\s*\d{4}|수정\s*\d{4}|Copyright|저작권|무단.*전재', text) and
                not text.startswith(('▶', '☞', '※', '■', '▲', '[', '◆', '○')) and
                '@' not in text or len([x for x in text if x == '@']) <= 1):
                content_parts.append(text)
        
        if content_parts:
            content = ' '.join(content_parts)
    
    return content

def clean_news_content(content, url):
    """뉴스 본문 정제"""
    if not content:
        return ""
    
    domain = urlparse(url).netloc.lower()
    
    # 공통 제거 패턴
    remove_patterns = [
        r'입력\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'수정\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'업데이트\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'무단.*전재.*금지',
        r'재배포.*금지',
        r'저작권.*무단.*전재',
        r'관련기사.*더보기',
        r'페이스북.*트위터.*카카오',
        r'구독.*신청',
        r'광고',
        r'연합뉴스.*제공',
        r'뉴시스.*제공',
        r'[가-힣]{2,4}\s*기자\s*[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+',  # 기자 이메일 제거
        r'ⓒ.*뉴스',
        r'Copyright.*\d{4}',
        r'All rights reserved',
    ]
    
    # 언론사별 특수 패턴
    if 'chosun.com' in domain:
        remove_patterns.extend([r'조선일보.*무단.*전재', r'chosun\.com'])
    elif 'donga.com' in domain:
        remove_patterns.extend([r'동아일보.*무단.*전재', r'donga\.com'])
    elif 'joongang.co.kr' in domain:
        remove_patterns.extend([r'중앙일보.*무단.*전재', r'joongang\.co\.kr'])
    elif 'hankyung.com' in domain:
        remove_patterns.extend([r'한국경제.*무단.*전재', r'hankyung\.com', r'한경닷컴'])
    
    for pattern in remove_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 공백 정리
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 길이 제한
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    return content

def fetch_google_news_rss_to_csv(rss_url, output_file, max_articles=30):
    """구글뉴스 RSS를 파싱하여 CSV로 저장"""
    
    print(f"구글뉴스 RSS 피드 파싱 중: {rss_url}")
    
    # RSS 파싱
    try:
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        feed = feedparser.parse(response.content)
    except:
        feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        print("❌ RSS 피드에서 기사를 찾을 수 없습니다.")
        return
    
    print(f"✅ RSS에서 {len(feed.entries)}개 기사 발견")
    
    success_count = 0
    total_count = min(len(feed.entries), max_articles)
    
    # CSV 파일 생성
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['제목', '날짜', '언론사', '기자명', '본문', '원본URL']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"총 {total_count}개 기사 처리 시작...\n")
        
        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                
                link = entry.link
                
                # 언론사 추출
                source = ""
                if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                    source = entry.source.title.strip()
                
                # RSS 요약 정보 추출
                summary = ""
                if hasattr(entry, 'description'):
                    summary = entry.description.strip()
                    summary = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', summary, flags=re.DOTALL)
                    summary = re.sub(r'<[^>]+>', '', summary)  # HTML 태그 제거
                    summary = clean_news_content(summary, link)
                
                # 날짜 형식 변환
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"[{i+1}/{total_count}] {title[:50]}... (출처: {source})")
                
                # 기사 본문 및 기자명 추출
                reporter, content = extract_google_news_content(link, summary)
                
                # 실제 URL 추출
                actual_url = extract_actual_url_from_google_news(link)
                
                # 최소 조건 확인
                if len(content.strip()) < 30:
                    print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                    continue
                
                # CSV에 쓰기
                writer.writerow({
                    '제목': title,
                    '날짜': date,
                    '언론사': source if source else "미상",
                    '기자명': reporter if reporter else "미상",
                    '본문': content,
                    '원본URL': actual_url if actual_url else link
                })
                
                success_count += 1
                print(f"    ✅ 성공! (언론사: {source}, 기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)")
                
                # 진행률 표시
                if (i + 1) % 3 == 0:
                    print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                    print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")
                
                # 랜덤 딜레이 (서버 부하 방지) - 구글뉴스는 더 긴 딜레이 필요
                delay = random.uniform(2.0, 4.0)
                time.sleep(delay)
                
            except KeyboardInterrupt:
                print("\n⚠ 사용자가 중단했습니다.")
                break
            except Exception as e:
                print(f"    ❌ 오류: {e}")
                continue
        
        print(f"\n{'='*70}")
        print(f"🎉 완료! CSV 파일 저장: {output_file}")
        print(f"📊 최종 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
        print(f"{'='*70}")

# 사용 예시
if __name__ == "__main__":
    # 구글뉴스 RSS URL 옵션들 (첨부된 이미지 기반)
    google_news_rss_options = {
        "전체뉴스": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&output=rss",
        "주요뉴스": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=h&output=rss",
        "정치": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=p&output=rss",
        "경제": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=b&output=rss",
        "사회": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=y&output=rss",
        "문화/생활": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=l&output=rss",
        "국제": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=w&output=rss",
        "정보과학": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=t&output=rss",
        "건강": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=m&output=rss",
        "스포츠": "http://news.google.co.kr/news?pz=1&cf=all&ned=kr&hl=ko&topic=s&output=rss"
    }
    
    # 원하는 카테고리 선택
    print("구글뉴스 RSS 수집기")
    print("="*50)
    for key in google_news_rss_options.keys():
        print(f"- {key}")
    
    # 카테고리 입력 받기
    selected_category = input("\n수집할 카테고리를 입력하세요 (기본값: 전체뉴스): ").strip()
    if not selected_category or selected_category not in google_news_rss_options:
        selected_category = "전체뉴스"
    
    # 기사 수 입력 받기
    try:
        max_articles = int(input("수집할 기사 수를 입력하세요 (기본값: 15): ").strip() or "15")
    except:
        max_articles = 15
    
    selected_rss = google_news_rss_options[selected_category]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"results/google_news_{selected_category}_{timestamp}.csv"
    
    print(f"\n🚀 {selected_category} 카테고리에서 {max_articles}개 기사 수집 시작!")
    print(f"📁 저장 파일: {output_file}\n")
    
    # 실행
    fetch_google_news_rss_to_csv(selected_rss, output_file, max_articles)
