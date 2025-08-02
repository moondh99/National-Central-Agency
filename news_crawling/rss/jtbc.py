import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random

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

def extract_jtbc_article_content(url, rss_summary=""):
    """JTBC 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://news-ex.jtbc.co.kr/',
            'Cache-Control': 'no-cache'
        }
        
        print(f"    접속 시도: {url[:80]}...")
        
        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get('https://news-ex.jtbc.co.kr/', headers=headers, timeout=5)
            time.sleep(0.5)
            
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if len(response.content) < 3000:  # 3KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")
                
        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        full_text = soup.get_text()
        
        # 기자명 추출 - JTBC 패턴에 맞게 수정
        reporter = ""
        reporter_patterns = [
            r'([가-힣]{2,4})\s*기자\s*([a-zA-Z0-9_.+-]+@jtbc\.co\.kr)',           # 기자명 기자 이메일@jtbc.co.kr
            r'([가-힣]{2,4})\s*기자\s*[a-zA-Z0-9_.+-]+@jtbc\.co\.kr',              # 기자명 기자 이메일
            r'([가-힣]{2,4})\s*기자',                                              # 기자명 기자
            r'기자\s*([가-힣]{2,4})',                                              # 기자 기자명
            r'([가-힣]{2,4})\s*특파원',                                            # 기자명 특파원
            r'([가-힣]{2,4})\s*앵커',                                              # 기자명 앵커
            r'([가-힣]{2,4})\s*아나운서',                                          # 기자명 아나운서
            r'([가-힣]{2,4})\s*기자\s*=',                                          # 기자명 기자 =
            r'취재\s*([가-힣]{2,4})',                                              # 취재 기자명
            r'글\s*([가-힣]{2,4})',                                                # 글 기자명
            r'([가-힣]{2,4})\s*선임기자',                                          # 기자명 선임기자
            r'([가-힣]{2,4})\s*수석기자',                                          # 기자명 수석기자
            r'([가-힣]{2,4})\s*논설위원',                                          # 기자명 논설위원
            r'JTBC\s*([가-힣]{2,4})',                                             # JTBC 기자명
        ]
        
        # 기사 본문 끝 부분에서 기자명을 찾는 것이 더 정확
        article_end = full_text[-1500:]  # 마지막 1500자에서 찾기
        
        for pattern in reporter_patterns:
            match = re.search(pattern, article_end)
            if match:
                reporter = match.group(1)
                reporter = re.sub(r'기자|특파원|앵커|아나운서|취재|글|선임기자|수석기자|논설위원|JTBC', '', reporter).strip()
                if len(reporter) >= 2 and len(reporter) <= 4:
                    break
        
        # 본문 추출 - JTBC HTML 구조에 맞게 수정
        content = ""
        
        # 방법 1: JTBC 기사 본문 구조 찾기
        content_selectors = [
            'div.article_content',       # JTBC 주요 기사 본문 클래스
            'div[class*="article"]',     # article 관련 클래스
            'div[class*="content"]',     # content 관련 클래스
            'div[class*="news"]',        # news 관련 클래스
            'div[class*="text"]',        # text 관련 클래스
            'div.news_content',          # 뉴스 컨텐츠
            'div.view_content',          # 뷰 컨텐츠
            'article',                   # article 태그
            'main',                      # main 태그
            'div[id*="article"]',        # article ID 관련
            'div.bodycontent',           # 바디 컨텐츠
            'div.story',                 # 스토리 컨텐츠
            'div.article_body',          # 기사 본문
            'div.articleView',           # 기사 뷰
            'div.news_body',             # 뉴스 바디
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if len(text) > len(content):
                    content = text
        
        # 방법 2: P 태그 기반 추출 (JTBC 특성에 맞게 수정)
        if len(content) < 200:
            paragraphs = soup.find_all('p')
            content_parts = []
            
            for p in paragraphs:
                text = p.get_text().strip()
                if (len(text) > 20 and 
                    not re.search(r'입력\s*\d{4}|수정\s*\d{4}|Copyright|저작권|JTBC|jtbc', text) and
                    not text.startswith(('▶', '☞', '※', '■', '▲', '[', '※', '◆', '○', '△')) and
                    '@jtbc.co.kr' not in text and
                    '무단 전재' not in text and
                    '재배포 금지' not in text and
                    '기사제보' not in text and
                    '뉴스룸' not in text):
                    content_parts.append(text)
            
            if content_parts:
                content = ' '.join(content_parts)
        
        # 본문 정제
        content = clean_jtbc_content(content)
        
        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")
        
        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content
        
    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"

def clean_jtbc_content(content):
    """JTBC 기사 본문 정제"""
    if not content:
        return ""
    
    # 불필요한 문구들 제거 - JTBC 특성에 맞게 수정
    remove_patterns = [
        r'입력\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'수정\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'업데이트\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}',
        r'JTBC.*무단.*전재.*금지',
        r'무단.*전재.*재배포.*금지',
        r'저작권.*JTBC',
        r'관련기사.*더보기',
        r'페이스북.*트위터.*카카오',
        r'구독.*신청',
        r'광고',
        r'[가-힣]{2,4}\s*기자\s*[a-zA-Z0-9_.+-]+@jtbc\.co\.kr',  # 기자 이메일 제거
        r'연합뉴스.*제공',          # 뉴스 출처 제거
        r'뉴시스.*제공',            # 뉴스 출처 제거
        r'JTBC.*제공',              # 사진 출처 제거
        r'ⓒ.*JTBC',
        r'jtbc\.co\.kr',
        r'기사제보.*문의',
        r'독자투고.*문의',
        r'청소년.*보호.*책임자',
        r'개인정보.*처리.*방침',
        r'이메일.*무단.*수집.*거부',
        r'Copyright.*\d{4}.*JTBC',
        r'뉴스룸.*앵커',
        r'이 시각.*뉴스',
        r'JTBC.*뉴스',
    ]
    
    for pattern in remove_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 공백 정리
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 길이 제한
    if len(content) > 1800:
        content = content[:1800] + "..."
    
    return content

def fetch_jtbc_rss_to_csv(rss_url, output_file, max_articles=30):
    """JTBC RSS를 파싱하여 CSV로 저장"""
    
    print(f"JTBC RSS 피드 파싱 중: {rss_url}")
    
    # RSS 파싱
    try:
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        # JTBC RSS는 UTF-8 인코딩 사용
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
        fieldnames = ['제목', '날짜', '카테고리', '기자명', '본문']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"총 {total_count}개 기사 처리 시작...\n")
        
        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                
                link = entry.link
                
                # 카테고리 추출 (JTBC RSS 구조에 맞게)
                category = ""
                if hasattr(entry, 'category'):
                    category = entry.category.strip()
                elif hasattr(entry, 'tags') and entry.tags:
                    category = entry.tags[0].term if entry.tags else ""
                
                # URL에서 카테고리 추출 시도 (JTBC URL 구조 기반)
                if not category:
                    url_category_map = {
                        # 주요뉴스
                        'newsflash': '속보',
                        'issue': '이슈 Top10',
                        
                        # 분야별 뉴스
                        'politics': '정치',
                        'economy': '경제',
                        'society': '사회',
                        'international': '국제',
                        'culture': '문화',
                        'sports': '스포츠',
                        'entertainment': '연예',
                        'weather': '날씨',
                    }
                    
                    for url_part, cat_name in url_category_map.items():
                        if url_part in rss_url:
                            category = cat_name
                            break
                
                # RSS 요약 정보 추출
                summary = ""
                if hasattr(entry, 'description'):
                    summary = entry.description.strip()
                    # HTML 태그와 CDATA 제거
                    summary = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', summary, flags=re.DOTALL)
                    summary = re.sub(r'<[^>]+>', '', summary)  # HTML 태그 제거
                    summary = clean_jtbc_content(summary)
                
                # 날짜 형식 변환
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"[{i+1}/{total_count}] {title[:50]}...")
                
                # 기사 본문 및 기자명 추출
                reporter, content = extract_jtbc_article_content(link, summary)
                
                # 최소 조건 확인
                if len(content.strip()) < 20:
                    print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                    continue
                
                # CSV에 쓰기
                writer.writerow({
                    '제목': title,
                    '날짜': date,
                    '카테고리': category if category else "미분류",
                    '기자명': reporter if reporter else "미상",
                    '본문': content
                })
                
                success_count += 1
                print(f"    ✅ 성공! (카테고리: {category}, 기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)")
                
                # 진행률 표시
                if (i + 1) % 5 == 0:
                    print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                    print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")
                
                # 랜덤 딜레이 (서버 부하 방지)
                delay = random.uniform(2.0, 4.0)  # JTBC는 조금 더 긴 딜레이
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
    # JTBC RSS URL 옵션들 (첨부된 이미지 기반)
    jtbc_rss_options = {
        # 주요뉴스
        "속보": "https://news-ex.jtbc.co.kr/v1/get/rss/newsflash",
        "이슈 Top10": "https://news-ex.jtbc.co.kr/v1/get/rss/issue",
        
        # 분야별 뉴스
        "정치": "https://news-ex.jtbc.co.kr/v1/get/rss/section/politics",
        "경제": "https://news-ex.jtbc.co.kr/v1/get/rss/section/economy",
        "사회": "https://news-ex.jtbc.co.kr/v1/get/rss/section/society",
        "국제": "https://news-ex.jtbc.co.kr/v1/get/rss/section/international",
        "문화": "https://news-ex.jtbc.co.kr/v1/get/rss/section/culture",
        "스포츠": "https://news-ex.jtbc.co.kr/v1/get/rss/section/sports",
        "연예": "https://news-ex.jtbc.co.kr/v1/get/rss/section/entertainment",
        "날씨": "https://news-ex.jtbc.co.kr/v1/get/rss/section/weather"
    }
    
    # 원하는 카테고리 선택
    print("JTBC RSS 수집기")
    print("="*50)
    print("주요뉴스:")
    for key in ["속보", "이슈 Top10"]:
        print(f"- {key}")
    
    print("\n분야별 뉴스:")
    for key in ["정치", "경제", "사회", "국제", "문화", "스포츠", "연예", "날씨"]:
        print(f"- {key}")
    
    # 카테고리 입력 받기
    selected_category = input("\n수집할 카테고리를 입력하세요 (기본값: 속보): ").strip()
    if not selected_category or selected_category not in jtbc_rss_options:
        selected_category = "속보"
    
    # 기사 수 입력 받기
    try:
        max_articles = int(input("수집할 기사 수를 입력하세요 (기본값: 15): ").strip() or "15")
    except:
        max_articles = 15
    
    selected_rss = jtbc_rss_options[selected_category]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"results/jtbc_{selected_category}_{timestamp}.csv"
    
    print(f"\n🚀 {selected_category} 카테고리에서 {max_articles}개 기사 수집 시작!")
    print(f"📁 저장 파일: {output_file}\n")
    
    # 실행
    fetch_jtbc_rss_to_csv(selected_rss, output_file, max_articles)
