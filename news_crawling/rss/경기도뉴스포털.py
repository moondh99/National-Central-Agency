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

def extract_gnews_article_content(url, rss_summary=""):
    """경기도 뉴스포털 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://gnews.gg.go.kr/',
            'Cache-Control': 'no-cache'
        }
        
        print(f"    접속 시도: {url[:80]}...")
        
        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get('https://gnews.gg.go.kr/', headers=headers, timeout=5)
            time.sleep(0.5)
            
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 경기도 뉴스포털은 일반적으로 접근 제한이 없음
            if len(response.content) < 3000:  # 3KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")
                
        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        full_text = soup.get_text()
        
        # 기자명 추출 - 안전한 패턴만 사용
        reporter = ""
        
        # 경기도 뉴스포털은 RSS에서 기자명이 제공되므로 우선 확인
        if '|' in rss_summary:
            parts = rss_summary.split('|')
            if len(parts) >= 2:
                potential_reporter = parts[0].strip()
                if len(potential_reporter) >= 2 and len(potential_reporter) <= 10:
                    reporter = potential_reporter
        
        # 다른 패턴들도 시도 (안전한 정규식만 사용)
        if not reporter:
            # RSS 요약과 본문에서 기자명 찾기
            search_text = rss_summary + " " + full_text[-1000:]
            
            # 한글 이름 패턴 (2-4글자)
            korean_name_pattern = r'([가-힣]{2,4})'
            
            # 기자명 패턴들
            if '기자' in search_text:
                match = re.search(korean_name_pattern + r'\s*기자', search_text)
                if match:
                    reporter = match.group(1)
            elif '특파원' in search_text:
                match = re.search(korean_name_pattern + r'\s*특파원', search_text)
                if match:
                    reporter = match.group(1)
            elif '기회기자단' in search_text:
                match = re.search(r'기회기자단\s*' + korean_name_pattern, search_text)
                if match:
                    reporter = match.group(1)
        
        # 본문 추출 - 다양한 방법 시도
        content = ""
        
        # 방법 1: 특정 태그에서 추출
        content_tags = ['div', 'article', 'main', 'section']
        for tag in content_tags:
            elements = soup.find_all(tag)
            for element in elements:
                text = element.get_text().strip()
                # 긴 텍스트를 본문으로 간주
                if len(text) > len(content) and len(text) > 100:
                    content = text
        
        # 방법 2: P 태그들을 모두 합치기
        if len(content) < 200:
            paragraphs = soup.find_all('p')
            content_parts = []
            
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 20:
                    # 불필요한 텍스트 제외
                    if not any(skip_word in text for skip_word in ['ⓒ', '#경기', '#Gyeonggi', '내일이 먼저']):
                        content_parts.append(text)
            
            if content_parts:
                content = ' '.join(content_parts)
        
        # 방법 3: 전체 텍스트에서 추출
        if len(content) < 100:
            lines = full_text.split('\n')
            content_lines = []
            
            for line in lines:
                line = line.strip()
                if len(line) > 30:  # 충분히 긴 라인만
                    # 불필요한 라인 제외
                    if not any(skip_word in line for skip_word in ['ⓒ', '#경기', '#Gyeonggi', '내일이 먼저']):
                        content_lines.append(line)
            
            if content_lines:
                content = ' '.join(content_lines[:10])  # 처음 10개 라인만
        
        # 본문 정제
        content = clean_gnews_content(content)
        
        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")
        
        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content
        
    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"

def clean_gnews_content(content):
    """경기도 뉴스포털 기사 본문 정제 - 안전한 방법 사용"""
    if not content:
        return ""
    
    # 문자열 치환으로 불필요한 내용 제거 (정규식 사용 최소화)
    
    # 저작권 표시 제거
    content = content.replace('ⓒ 경기도청', '')
    content = content.replace('ⓒ 경기도', '')
    content = content.replace('내일이 먼저 시작되는 경기.', '')
    
    # 해시태그 제거 (간단한 방법)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        if not line.strip().startswith('#'):
            cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    
    # 공백 정리 (안전한 정규식만 사용)
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 길이 제한
    if len(content) > 1500:
        content = content[:1500] + "..."
    
    return content

def fetch_gnews_rss_to_csv(rss_url, output_file, max_articles=30):
    """경기도 뉴스포털 RSS를 파싱하여 CSV로 저장"""
    
    print(f"경기도 뉴스포털 RSS 피드 파싱 중: {rss_url}")
    
    # RSS 파싱
    try:
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
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
        fieldnames = ['제목', '날짜', '링크', '기자명', '본문']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"총 {total_count}개 기사 처리 시작...\n")
        
        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                # CDATA 제거 (안전한 방법)
                if '<![CDATA[' in title:
                    title = title.replace('<![CDATA[', '').replace(']]>', '')
                
                link = entry.link
                
                # RSS 요약 정보 추출
                summary = ""
                if hasattr(entry, 'description'):
                    summary = entry.description.strip()
                    # HTML 태그 제거 (안전한 방법)
                    summary = re.sub(r'<[^>]+>', '', summary)
                    summary = clean_gnews_content(summary)
                elif hasattr(entry, 'summary'):
                    summary = entry.summary.strip()
                    summary = re.sub(r'<[^>]+>', '', summary)
                    summary = clean_gnews_content(summary)
                
                # 날짜 형식 변환
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                elif hasattr(entry, 'pubdate_parsed') and entry.pubdate_parsed:
                    date = datetime(*entry.pubdate_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"[{i+1}/{total_count}] {title[:60]}...")
                
                # 기사 본문 및 기자명 추출
                reporter, content = extract_gnews_article_content(link, summary)
                
                # 최소 조건 확인
                if len(content.strip()) < 20:
                    print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                    continue
                
                # CSV에 쓰기
                writer.writerow({
                    '제목': title,
                    '날짜': date,
                    '링크': link,
                    '기자명': reporter if reporter else "미상",
                    '본문': content
                })
                
                success_count += 1
                print(f"    ✅ 성공! (기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)")
                
                # 진행률 표시
                if (i + 1) % 5 == 0:
                    print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                    print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")
                
                # 랜덤 딜레이 (서버 부하 방지)
                delay = random.uniform(1.5, 2.5)
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
    # 경기도 뉴스포털 RSS URL 옵션들
    gnews_rss_options = {
        "정치": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E001&policyCode=E001",
        "복지": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E002&policyCode=E002",
        "교육": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E003&policyCode=E003",
        "주택": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E004&policyCode=E004",
        "환경": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E005&policyCode=E005",
        "문화": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E006&policyCode=E006",
        "교통": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E007&policyCode=E007",
        "안전": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E008&policyCode=E008",
        "보도자료": "https://gnews.gg.go.kr/rss/gnewsRssBodo.do",
        "경기뉴스광장": "https://gnews.gg.go.kr/rss/gnewsZoneRss.do",
        "일일뉴스": "https://gnews.gg.go.kr/rss/gnewsDailyRss.do",
        "나의경기도": "https://gnews.gg.go.kr/rss/gnewsMyGyeonggiRss.do"
    }
    
    # 원하는 카테고리 선택
    print("경기도 뉴스포털 RSS 수집기")
    print("="*50)
    for key, value in gnews_rss_options.items():
        print(f"- {key}")
    
    # 카테고리 입력 받기
    selected_category = input("\n수집할 카테고리를 입력하세요 (기본값: 보도자료): ").strip()
    if not selected_category or selected_category not in gnews_rss_options:
        selected_category = "보도자료"
    
    # 기사 수 입력 받기
    try:
        max_articles = int(input("수집할 기사 수를 입력하세요 (기본값: 20): ").strip() or "20")
    except:
        max_articles = 20
    
    selected_rss = gnews_rss_options[selected_category]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"results/gnews_{selected_category}_{timestamp}.csv"
    
    print(f"\n🚀 {selected_category} 카테고리에서 {max_articles}개 기사 수집 시작!")
    print(f"📁 저장 파일: {output_file}\n")
    
    # 실행
    fetch_gnews_rss_to_csv(selected_rss, output_file, max_articles)
