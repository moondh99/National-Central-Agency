import requests
from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
import time
from urllib.parse import urljoin, urlparse

def extract_dailian_article_content(url):
    """데일리안 기사 URL에서 전체 본문을 추출하는 함수"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 데일리안 기사 본문 추출
        content_selectors = [
            'div.article_txt',           # 주요 본문 영역
            'div.news_article_body',     # 뉴스 기사 본문
            'div.view_con',              # 본문 컨테이너
            'div.article-body',          # 기사 본문
            'div.news_view',             # 뉴스 뷰
            '.article_content',          # 기사 컨텐츠
            'div.txt_area',              # 텍스트 영역
            '#article_content'           # ID 기반 본문
        ]
        
        full_content = ""
        
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    # 불필요한 요소들 제거
                    for unwanted in element.find_all(['script', 'style', 'iframe', 'ins', 'div.ad', '.advertisement', '.related-articles', '.tags', '.share']):
                        unwanted.decompose()
                    
                    # 텍스트 추출
                    text = element.get_text(separator='\n', strip=True)
                    if text and len(text) > len(full_content):
                        full_content = text
                        break
                
                if full_content:
                    break
        
        # 본문이 여전히 짧다면 p 태그들로 재시도
        if len(full_content) < 100:
            paragraphs = soup.find_all('p')
            paragraph_texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20 and '©' not in text and 'Copyright' not in text:
                    paragraph_texts.append(text)
            
            if paragraph_texts:
                candidate_content = '\n'.join(paragraph_texts)
                if len(candidate_content) > len(full_content):
                    full_content = candidate_content
        
        # 텍스트 정리
        if full_content:
            # 저작권 표시 제거
            full_content = re.sub(r'©.*?데일리안.*?금지.*?$', '', full_content, flags=re.MULTILINE)
            full_content = re.sub(r'Copyright.*?dailian.*?$', '', full_content, flags=re.MULTILINE | re.IGNORECASE)
            # 연속된 공백과 줄바꿈 정리
            full_content = re.sub(r'\n+', '\n', full_content)
            full_content = re.sub(r'\s+', ' ', full_content)
            full_content = full_content.strip()
        
        return full_content
        
    except Exception as e:
        print(f"본문 추출 중 오류: {e}")
        return ""

def extract_dailian_reporter_name(soup, article_text):
    """데일리안 기자명을 추출하는 함수"""
    try:
        # 데일리안의 기자명 추출 패턴
        reporter_patterns = [
            # HTML에서 기자명 추출
            r'<span[^>]*class[^>]*reporter[^>]*>([^<]+)</span>',
            r'<div[^>]*class[^>]*reporter[^>]*>([^<]+)</div>',
            r'<p[^>]*class[^>]*reporter[^>]*>([^<]+)</p>',
            
            # 텍스트에서 기자명 추출 (데일리안 특성에 맞게)
            r'([가-힣]{2,4})\s*기자(?:\s*=|\s*∙|\s*·|\s*입력|\s*수정|\s*작성)',
            r'기자\s*([가-힣]{2,4})(?:\s*=|\s*∙|\s*·)',
            r'([가-힣]{2,4})\s*특파원',
            r'([가-힣]{2,4})\s*논설위원',
            r'([가-힣]{2,4})\s*편집위원',
            r'/\s*([가-힣]{2,4})\s*기자',
            r'=\s*([가-힣]{2,4})\s*기자',
            r'∙\s*([가-힣]{2,4})\s*기자',
            r'·\s*([가-힣]{2,4})\s*기자',
            r'기자\s*:\s*([가-힣]{2,4})',
            r'\[([가-힣]{2,4})\s*기자\]'
        ]
        
        # BeautifulSoup 객체에서 기자명 찾기
        if soup:
            # 기자명이 포함될 가능성이 있는 요소들 찾기
            reporter_elements = soup.find_all(['span', 'div', 'p'], string=re.compile(r'기자|특파원|논설위원'))
            for element in reporter_elements:
                text = element.get_text(strip=True)
                if '기자' in text:
                    match = re.search(r'([가-힣]{2,4})', text)
                    if match:
                        return match.group(1) + ' 기자'
        
        # 기사 텍스트에서 기자명 찾기
        full_text = str(soup) + '\n' + article_text if soup else article_text
        
        for pattern in reporter_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                reporter = matches[0].strip()
                if reporter and len(reporter) >= 2:
                    return reporter + (' 기자' if '기자' not in reporter else '')
        
        return "기자명 없음"
        
    except Exception as e:
        print(f"기자명 추출 중 오류: {e}")
        return "기자명 없음"

def get_dailian_news_list(base_url="https://www.dailian.co.kr", max_pages=3):
    """데일리안 뉴스 목록을 가져오는 함수"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        news_items = []
        
        # 여러 페이지에서 뉴스 수집
        for page in range(1, max_pages + 1):
            try:
                # 데일리안 뉴스 목록 페이지 (최신순)
                list_url = f"{base_url}/news/list/?page={page}"
                
                print(f"📄 {page}페이지 뉴스 목록을 가져오는 중...")
                
                response = requests.get(list_url, headers=headers, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 뉴스 링크들 찾기 (다양한 선택자 시도)
                link_selectors = [
                    'a[href*="/news/view/"]',      # 뉴스 뷰 링크
                    'h3 a, h2 a, .title a',       # 제목 링크
                    '.news_list a',                # 뉴스 리스트 링크
                    '.article_list a'              # 기사 리스트 링크
                ]
                
                page_links = []
                for selector in link_selectors:
                    links = soup.select(selector)
                    if links:
                        page_links.extend(links)
                        break
                
                # 중복 제거 및 유효한 링크만 선별
                seen_urls = set()
                for link in page_links:
                    href = link.get('href')
                    if href and '/news/view/' in href:
                        full_url = urljoin(base_url, href)
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            
                            # 제목 추출
                            title = link.get_text(strip=True)
                            if not title:
                                title_elem = link.find_parent().find(['h1', 'h2', 'h3', 'h4'])
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                            
                            if title and len(title) > 5:  # 너무 짧은 제목 제외
                                news_items.append({
                                    'url': full_url,
                                    'title': title[:100]  # 제목 길이 제한
                                })
                
                new_items = news_items[-len(page_links):] if page_links else []
                print(f"  ➤ {page}페이지에서 {len(new_items)} 개 새로운 뉴스 발견")
                
                time.sleep(1)  # 페이지 요청 간 딜레이
                
            except Exception as e:
                print(f"  ➤ {page}페이지 처리 중 오류: {e}")
                continue
        
        # 중복 제거
        unique_news = []
        seen_urls = set()
        for item in news_items:
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                unique_news.append(item)
        
        print(f"📊 총 {len(unique_news)}개의 고유한 뉴스를 발견했습니다.")
        return unique_news
        
    except Exception as e:
        print(f"뉴스 목록 수집 중 오류: {e}")
        return []

def scrape_dailian_news(max_articles=50, max_pages=3):
    """데일리안 뉴스를 크롤링하여 CSV로 저장하는 메인 함수"""
    
    print("🗞️  데일리안 뉴스 크롤링 시작")
    print("=" * 60)
    
    try:
        # 뉴스 목록 가져오기
        news_list = get_dailian_news_list(max_pages=max_pages)
        
        if not news_list:
            print("❌ 뉴스 목록을 가져올 수 없습니다.")
            return None
        
        # 최대 기사 수 제한
        if len(news_list) > max_articles:
            news_list = news_list[:max_articles]
            print(f"⚠️  최대 {max_articles}개 기사로 제한합니다.")
        
        news_data = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print(f"\n📰 {len(news_list)}개 기사의 상세 정보를 수집합니다...")
        
        for i, news_item in enumerate(news_list):
            try:
                url = news_item['url']
                base_title = news_item['title']
                
                print(f"[{i+1}/{len(news_list)}] 처리 중: {base_title[:50]}...")
                
                # 개별 기사 페이지 크롤링
                response = requests.get(url, headers=headers, timeout=20)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 제목 추출 (더 정확한 제목)
                title = base_title
                title_selectors = ['h1.title', 'h1', '.news_title', '.article_title', 'title']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        extracted_title = title_elem.get_text(strip=True)
                        if extracted_title and len(extracted_title) > len(title):
                            title = extracted_title
                        break
                
                # 날짜 추출
                date_text = "날짜 없음"
                date_selectors = [
                    '.date', '.news_date', '.article_date', '.view_date',
                    '[class*="date"]', '[class*="time"]'
                ]
                
                for selector in date_selectors:
                    date_elem = soup.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        break
                
                # 날짜 형식 정리
                if date_text != "날짜 없음":
                    # 한국 날짜 형식 처리
                    date_match = re.search(r'(\d{4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})', date_text)
                    if date_match:
                        year, month, day = date_match.groups()
                        date_text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    # 시간 정보가 있다면 추가
                    time_match = re.search(r'(\d{1,2}):(\d{2})', date_text)
                    if time_match:
                        hour, minute = time_match.groups()
                        date_text += f" {hour.zfill(2)}:{minute}"
                
                # 전체 본문 추출
                full_content = extract_dailian_article_content(url)
                
                # 기자명 추출
                reporter_name = extract_dailian_reporter_name(soup, full_content)
                
                # 데이터 저장
                if full_content.strip():  # 본문이 있는 경우만 저장
                    news_data.append({
                        '제목': title.strip(),
                        '날짜': date_text,
                        '기자명': reporter_name,
                        '본문': full_content
                    })
                else:
                    print(f"  ➤ 본문을 추출할 수 없어 건너뜁니다.")
                
                # 서버 부하 방지
                time.sleep(1.5)
                
            except Exception as e:
                print(f"  ➤ 기사 처리 중 오류: {e}")
                continue
        
        # CSV 파일로 저장
        if news_data:
            filename = f"results/데일리안_뉴스_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['제목', '날짜', '기자명', '본문']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(news_data)
            
            print(f"\n✅ 성공적으로 {len(news_data)}개의 뉴스를 저장했습니다!")
            print(f"📁 파일명: {filename}")
            
            # 통계 정보 출력
            total_chars = sum(len(item['본문']) for item in news_data)
            avg_chars = total_chars // len(news_data) if news_data else 0
            print(f"📊 평균 본문 길이: {avg_chars:,}자")
            print(f"📊 총 본문 길이: {total_chars:,}자")
            
            return filename
        else:
            print("❌ 추출된 뉴스 데이터가 없습니다.")
            return None
            
    except Exception as e:
        print(f"❌ 크롤링 중 오류 발생: {e}")
        return None

def scrape_dailian_by_category(category="all", max_articles=30):
    """카테고리별 데일리안 뉴스 크롤링"""
    
    category_urls = {
        "all": "https://www.dailian.co.kr/news/list/",
        "politics": "https://www.dailian.co.kr/news/list/?sc=politics",
        "economy": "https://www.dailian.co.kr/news/list/?sc=economy", 
        "society": "https://www.dailian.co.kr/news/list/?sc=society",
        "international": "https://www.dailian.co.kr/news/list/?sc=international",
        "culture": "https://www.dailian.co.kr/news/list/?sc=culture",
        "sports": "https://www.dailian.co.kr/news/list/?sc=sports",
        "it": "https://www.dailian.co.kr/news/list/?sc=it"
    }
    
    if category not in category_urls:
        print(f"❌ 지원하지 않는 카테고리입니다.")
        print(f"✅ 지원 카테고리: {', '.join(category_urls.keys())}")
        return None
    
    print(f"📰 {category} 카테고리 뉴스를 수집합니다.")
    
    # 카테고리별 맞춤 크롤링 로직은 위의 메인 함수와 동일하지만
    # URL만 카테고리별로 변경하여 사용
    return scrape_dailian_news(max_articles=max_articles, max_pages=2)

if __name__ == "__main__":
    print("🗞️  데일리안 뉴스 크롤링")
    print("=" * 60)
    
    try:
        print("\n📋 옵션을 선택하세요:")
        print("1. 전체 최신 뉴스 (50개)")
        print("2. 빠른 테스트 (10개)")
        print("3. 대량 수집 (100개)")
        
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == "1":
            print("\n🚀 전체 최신 뉴스 50개를 수집합니다...")
            result = scrape_dailian_news(max_articles=50, max_pages=3)
            
        elif choice == "2":
            print("\n🚀 테스트 모드 (10개 기사)로 시작합니다...")
            result = scrape_dailian_news(max_articles=10, max_pages=1)
            
        elif choice == "3":
            print("\n🚀 대량 수집 모드 (100개 기사)로 시작합니다...")
            result = scrape_dailian_news(max_articles=100, max_pages=5)
            
        else:
            print("⚠️  잘못된 선택입니다. 기본 모드로 진행합니다.")
            result = scrape_dailian_news(max_articles=30, max_pages=2)
        
        if result:
            print(f"\n🎉 완료! 파일이 저장되었습니다: {result}")
        else:
            print("\n❌ 작업이 실패했습니다.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
