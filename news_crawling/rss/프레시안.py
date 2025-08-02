import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

def extract_pressian_article_content(url):
    """프레시안 기사 URL에서 본문과 기자명을 추출"""
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
        
        # 기자명 추출 (프레시안 패턴)
        reporter = ""
        
        # 프레시안 기자명 패턴들
        reporter_patterns = [
            r'([가-힣]{2,4})\s*기자',  # 기자명 기자
            r'기자\s*([가-힣]{2,4})',  # 기자 기자명
            r'([가-힣]{2,4})\s*특파원',  # 기자명 특파원
            r'\/\s*([가-힣]{2,4})\s*기자',  # / 기자명 기자
        ]
        
        # 전체 텍스트에서 기자명 검색
        full_text = soup.get_text()
        for pattern in reporter_patterns:
            match = re.search(pattern, full_text[:500])  # 첫 500자에서 검색
            if match:
                reporter = match.group(1).strip()
                if len(reporter) >= 2 and len(reporter) <= 4:
                    break
        
        # 본문 추출 (프레시안 구조)
        content = ""
        
        # 불필요한 요소들 미리 제거
        for unwanted in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 
                                      'aside', 'figure', 'iframe', 'form']):
            unwanted.decompose()
        
        # 프레시안 본문 추출 (단락별로)
        paragraphs = soup.find_all('p')
        content_parts = []
        
        for p in paragraphs:
            text = p.get_text().strip()
            
            # 유효한 본문 문단인지 확인
            if (len(text) > 20 and 
                not re.search(r'구독료|계좌이체|프레시안협동조합|저작권|구독|댓글|공유|관련기사', text, re.IGNORECASE) and
                not text.startswith(('▶', '☞', '※', '■', '▲', '[', '●', '관련기사', '구독료를 내고 싶습니다')) and
                '기자' not in text or len(text) > 50):  # 기자명만 있는 짧은 문단 제외
                
                content_parts.append(text)
        
        content = ' '.join(content_parts)
        
        # 본문이 충분하지 않으면 전체 텍스트에서 추출
        if len(content) < 100:
            lines = full_text.split('\n')
            content_lines = []
            
            for line in lines:
                line = line.strip()
                if (len(line) > 30 and 
                    not re.search(r'구독료|계좌이체|프레시안협동조합|저작권|구독|댓글|공유|관련기사', line, re.IGNORECASE) and
                    not line.startswith(('▶', '☞', '※', '■', '▲', '[', '●'))):
                    content_lines.append(line)
            
            content = ' '.join(content_lines)
        
        # 본문 정제
        content = clean_pressian_content(content)
        
        return reporter, content
        
    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return "", ""

def clean_pressian_content(content):
    """프레시안 기사 본문 정제"""
    if not content:
        return ""
    
    # 프레시안 특화 불필요한 문구들 제거
    remove_patterns = [
        r'이\s*기사의\s*구독료를\s*내고\s*싶습니다',
        r'\d+,\d+\s*원?\s*추가',
        r'계좌이체도\s*가능합니다',
        r'프레시안협동조합.*후원금',
        r'일부\s*인터넷\s*환경에서는.*진행되지\s*않을\s*수\s*있습니다',
        r'저작권.*프레시안',
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
    ]
    
    for pattern in remove_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 여러 공백과 줄바꿈을 정리
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    return content

def fetch_pressian_rss_to_csv(rss_url, output_file, max_articles=50):
    """프레시안 RSS를 파싱하여 CSV로 저장"""
    
    print(f"프레시안 RSS 피드 파싱 중: {rss_url}")
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
                
                link = entry.link
                # RSS URL에서 &ref=rss 부분 제거
                link = re.sub(r'&ref=rss.*$', '', link)
                
                # 날짜 형식 변환
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"처리 중 [{i+1}/{total_count}]: {title[:50]}...")
                
                # 기사 본문 및 기자명 추출
                reporter, content = extract_pressian_article_content(link)
                
                # RSS description도 활용 가능
                rss_summary = ""
                if hasattr(entry, 'description'):
                    rss_summary = entry.description
                    # HTML 태그 제거
                    rss_summary = re.sub(r'<[^>]+>', '', rss_summary)
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
    # 프레시안 RSS URL 옵션들
    pressian_rss_options = {
        "최신기사": "http://www.pressian.com/api/v3/site/rss/news",
        "뉴스": "http://www.pressian.com/api/v3/site/rss/section/25",
        "books": "http://www.pressian.com/api/v3/site/rss/section/60",
        "세계": "http://www.pressian.com/api/v3/site/rss/section/65",
        "정치": "http://www.pressian.com/api/v3/site/rss/section/66",
        "경제": "http://www.pressian.com/api/v3/site/rss/section/67",
        "사회": "http://www.pressian.com/api/v3/site/rss/section/68",
        "문화": "http://www.pressian.com/api/v3/site/rss/section/69",
        "스포츠": "http://www.pressian.com/api/v3/site/rss/section/70",
        "미디어": "http://www.pressian.com/api/v3/site/rss/section/75"
    }
    
    # 사용할 RSS 선택
    selected_rss = pressian_rss_options["최신기사"]  # 원하는 카테고리로 변경
    
    # 파일명에 현재 시간 추가
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"results/pressian_{timestamp}.csv"
    
    # 최대 수집할 기사 수
    max_articles = 30
    
    # 실행
    fetch_pressian_rss_to_csv(selected_rss, output_file, max_articles)
