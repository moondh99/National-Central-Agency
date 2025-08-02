import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

def extract_ohmynews_article_content(url):
    """오마이뉴스 기사 URL에서 본문과 기자명을 추출"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 기자명은 RSS에서 이미 제공됨 (author 필드)
        reporter = ""  # RSS에서 가져올 예정
        
        # 본문 추출 (오마이뉴스는 비교적 간단한 구조)
        content = ""
        
        # 불필요한 요소들 미리 제거
        for unwanted in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 
                                      'aside', 'figure', 'iframe', 'form']):
            unwanted.decompose()
        
        # 오마이뉴스 본문 추출 (단락별로)
        paragraphs = soup.find_all('p')
        content_parts = []
        
        for p in paragraphs:
            text = p.get_text().strip()
            
            # 유효한 본문 문단인지 확인
            if (len(text) > 20 and 
                not re.search(r'copyright|저작권|오마이뉴스|구독|댓글|공유', text, re.IGNORECASE) and
                not text.startswith(('▶', '☞', '※', '■', '▲', '[', '●', '관련기사')) and
                '기자' not in text or len(text) > 50):  # 기자명만 있는 짧은 문단 제외
                
                content_parts.append(text)
        
        content = ' '.join(content_parts)
        
        # 본문이 충분하지 않으면 전체 텍스트에서 추출
        if len(content) < 100:
            full_text = soup.get_text()
            lines = full_text.split('\n')
            content_lines = []
            
            for line in lines:
                line = line.strip()
                if (len(line) > 30 and 
                    not re.search(r'copyright|저작권|오마이뉴스|구독|댓글|공유|관련기사', line, re.IGNORECASE) and
                    not line.startswith(('▶', '☞', '※', '■', '▲', '[', '●'))):
                    content_lines.append(line)
            
            content = ' '.join(content_lines)
        
        # 본문 정제
        content = clean_ohmynews_content(content)
        
        return reporter, content
        
    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return "", ""

def clean_ohmynews_content(content):
    """오마이뉴스 기사 본문 정제"""
    if not content:
        return ""
    
    # 오마이뉴스 특화 불필요한 문구들 제거
    remove_patterns = [
        r'Copyright.*오마이뉴스.*reserved',
        r'저작권.*오마이뉴스',
        r'구독.*신청',
        r'관련기사.*더보기',
        r'▶.*바로가기',
        r'☞.*클릭',
        r'※.*참조',
        r'■.*관련기사',
        r'▲.*사진.*ⓒ',
        r'페이스북.*트위터.*카카오',
        r'좋아요.*공유',
        r'댓글.*작성',
        r'전체.*내용보기',
    ]
    
    for pattern in remove_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 여러 공백과 줄바꿈을 정리
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    # 너무 짧거나 긴 경우 처리
    if len(content) < 50:
        return ""
    
    # 첫 1500자만 추출 (너무 긴 경우)
    if len(content) > 1500:
        content = content[:1500] + "..."
    
    return content

def fetch_ohmynews_rss_to_csv(rss_url, output_file, max_articles=50):
    """오마이뉴스 RSS를 파싱하여 CSV로 저장"""
    
    print(f"오마이뉴스 RSS 피드 파싱 중: {rss_url}")
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        print("RSS 피드에서 기사를 찾을 수 없습니다.")
        return
    
    success_count = 0
    total_count = min(len(feed.entries), max_articles)
    
    # CSV 파일 생성
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['제목', '날짜', '기자명', '본문']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"총 {total_count}개 기사 처리 중...")
        
        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                # CDATA 태그 제거
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                
                link = entry.link
                
                # RSS에서 기자명 추출 (오마이뉴스는 author 필드에 기자명 제공)
                reporter = ""
                if hasattr(entry, 'author') and entry.author:
                    reporter = entry.author.strip()
                
                # 날짜 형식 변환
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"처리 중 [{i+1}/{total_count}]: {title[:50]}...")
                
                # 기사 본문 추출
                _, content = extract_ohmynews_article_content(link)
                
                # RSS summary도 활용 가능
                rss_summary = ""
                if hasattr(entry, 'description'):
                    rss_summary = entry.description
                    # HTML 태그 제거
                    rss_summary = re.sub(r'<[^>]+>', '', rss_summary)
                    rss_summary = re.sub(r'전체.*내용보기', '', rss_summary)
                    rss_summary = rss_summary.strip()
                
                # 본문이 부족하면 RSS summary 사용
                if len(content) < 100 and len(rss_summary) > 100:
                    content = rss_summary
                    print(f"  RSS 요약 사용 (길이: {len(rss_summary)})")
                
                # 유효성 검사
                if len(content.strip()) < 30:
                    print(f"  ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})")
                    continue
                
                # CSV에 쓰기
                writer.writerow({
                    '제목': title,
                    '날짜': date,
                    '기자명': reporter if reporter else "미상",
                    '본문': content
                })
                
                success_count += 1
                print(f"  ✓ 완료 (기자: {reporter if reporter else '미상'})")
                
                # 서버 부하 방지를 위한 딜레이
                time.sleep(1)
                
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                continue
    
    print(f"\n{'='*50}")
    print(f"CSV 파일 저장 완료: {output_file}")
    print(f"성공적으로 처리된 기사: {success_count}/{total_count}")
    print(f"성공률: {success_count/total_count*100:.1f}%")
    print(f"{'='*50}")

# 사용 예시
if __name__ == "__main__":
    # 오마이뉴스 RSS URL 옵션들
    ohmynews_rss_options = {
        "전체기사": "https://rss.ohmynews.com/rss/ohmynews.xml",
        "주요기사": "https://rss.ohmynews.com/rss/top.xml",
        "정치": "https://rss.ohmynews.com/rss/politics.xml",
        "경제": "https://rss.ohmynews.com/rss/economy.xml",
        "사회": "https://rss.ohmynews.com/rss/society.xml",
        "문화": "https://rss.ohmynews.com/rss/culture.xml",
        "국제": "https://rss.ohmynews.com/rss/international.xml",
        "교육": "https://rss.ohmynews.com/rss/education.xml",
        "미디어": "https://rss.ohmynews.com/rss/media.xml",
        "여행": "https://rss.ohmynews.com/rss/travel.xml",
        "책동네": "https://rss.ohmynews.com/rss/book.xml",
        "여성": "https://rss.ohmynews.com/rss/woman.xml",
        "스포츠": "https://rss.ohmynews.com/rss/sports.xml",
        "오마이스타": "https://rss.ohmynews.com/rss/star.xml",
        "오마이TV": "https://rss.ohmynews.com/rss/ohmytv.xml"
    }
    
    # 사용할 RSS 선택
    selected_rss = ohmynews_rss_options["전체기사"]  # 원하는 카테고리로 변경
    
    # 파일명에 현재 시간 추가
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"results/ohmynews_{timestamp}.csv"
    
    # 최대 수집할 기사 수
    max_articles = 30
    
    # 실행
    fetch_ohmynews_rss_to_csv(selected_rss, output_file, max_articles)
